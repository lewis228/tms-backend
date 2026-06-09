# tests/integration/test_leg_reissue_dual.py
"""Dry Run 재발급 + Dual Transaction (Phase 4 재설계)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from leg.const.status import LegStatus
from leg.model import LegModel
from leg.service import LegService
from dual_transaction.const.status import DualTransactionStatus
from dual_transaction.service import DualTransactionService
from dual_transaction.schemas.request import DualTransactionCreateRequest

from tests.integration.factories import (
    make_customer, make_delivery_order, make_driver, make_leg, make_team, make_user,
)


@pytest.mark.asyncio
async def test_reissue_dry_run(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    driver = await make_driver(db_session, team=team)
    leg = await make_leg(db_session, team=team, do=do, driver_id=driver.id,
                         status=LegStatus.IN_TRANSIT)
    await db_session.commit()

    svc = LegService(db_session, team.id)
    new = await svc.reissue_dry_run(leg.id, reason="게이트 폐쇄", actor_user_id=user.id)

    # 새 leg — PENDING, 미배차, 원본 링크
    assert new.status == LegStatus.PENDING
    assert new.reissued_from_leg_id == leg.id
    assert new.driver_id is None

    # 원본 → DRY_RUN
    orig = (await db_session.execute(
        select(LegModel).where(LegModel.id == leg.id)
    )).scalar_one()
    assert orig.status == LegStatus.DRY_RUN
    assert orig.failure_reason == "게이트 폐쇄"


@pytest.mark.asyncio
async def test_reissue_requires_active_leg(db_session):
    from common.exceptions.base import BadRequestException
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    leg = await make_leg(db_session, team=team, do=do, status=LegStatus.PENDING)  # 미배차
    await db_session.commit()

    svc = LegService(db_session, team.id)
    with pytest.raises(BadRequestException, match="Dry Run"):
        await svc.reissue_dry_run(leg.id, actor_user_id=user.id)


@pytest.mark.asyncio
async def test_dual_transaction_pairs_and_assigns(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    driver = await make_driver(db_session, team=team)
    ret_leg = await make_leg(db_session, team=team, do=do, status=LegStatus.PENDING)
    pick_leg = await make_leg(db_session, team=team, do=do, status=LegStatus.PENDING)
    await db_session.commit()

    svc = DualTransactionService(db_session, team.id)
    dtx = await svc.create(DualTransactionCreateRequest(
        driver_id=driver.id, return_leg_id=ret_leg.id, pickup_leg_id=pick_leg.id,
    ), actor_user_id=user.id)

    assert dtx.status == DualTransactionStatus.PLANNED
    assert dtx.return_leg_id == ret_leg.id and dtx.pickup_leg_id == pick_leg.id

    # 두 leg 모두 driver 배차 + ASSIGNED
    legs = (await db_session.execute(
        select(LegModel).where(LegModel.id.in_([ret_leg.id, pick_leg.id]))
    )).scalars().all()
    assert all(l.driver_id == driver.id for l in legs)
    assert all(l.status == LegStatus.ASSIGNED for l in legs)


@pytest.mark.asyncio
async def test_dual_transaction_cancel(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    driver = await make_driver(db_session, team=team)
    ret_leg = await make_leg(db_session, team=team, do=do, status=LegStatus.PENDING)
    pick_leg = await make_leg(db_session, team=team, do=do, status=LegStatus.PENDING)
    await db_session.commit()

    svc = DualTransactionService(db_session, team.id)
    dtx = await svc.create(DualTransactionCreateRequest(
        driver_id=driver.id, return_leg_id=ret_leg.id, pickup_leg_id=pick_leg.id,
    ), actor_user_id=user.id)
    cancelled = await svc.cancel(dtx.id, actor_user_id=user.id)
    assert cancelled.status == DualTransactionStatus.CANCELLED
