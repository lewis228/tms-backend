# tests/integration/test_leg_transition.py
"""LegService.transition 라이프사이클 + Settlement 자동 생성."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from leg.const.status import LegStatus
from leg.service import LegService
from settlement.model import SettlementModel

from tests.integration.factories import (
    make_customer, make_delivery_order, make_driver, make_leg, make_team,
)


@pytest.mark.asyncio
async def test_pending_to_in_transit_sets_started_at(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    driver = await make_driver(db_session, team=team)
    leg = await make_leg(db_session, team=team, do=do, driver_id=driver.id)
    await db_session.commit()

    svc = LegService(db_session, team.id)
    await svc.transition(leg.id, LegStatus.IN_TRANSIT)

    refreshed = (await db_session.execute(
        select(type(leg)).where(type(leg).id == leg.id)
    )).scalar_one()
    assert refreshed.status == LegStatus.IN_TRANSIT
    assert refreshed.started_at is not None
    assert refreshed.completed_at is None


@pytest.mark.asyncio
async def test_in_transit_to_completed_creates_settlement(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    driver = await make_driver(db_session, team=team)
    leg = await make_leg(
        db_session, team=team, do=do, driver_id=driver.id,
        status=LegStatus.IN_TRANSIT,
    )
    await db_session.commit()

    svc = LegService(db_session, team.id)
    await svc.transition(leg.id, LegStatus.COMPLETED)

    refreshed = (await db_session.execute(
        select(type(leg)).where(type(leg).id == leg.id)
    )).scalar_one()
    assert refreshed.status == LegStatus.COMPLETED
    assert refreshed.completed_at is not None
    assert refreshed.arrived_at is not None

    # Settlement 자동 생성 확인
    s = (await db_session.execute(
        select(SettlementModel).where(SettlementModel.leg_id == leg.id)
    )).scalar_one_or_none()
    assert s is not None
    assert s.team_id == team.id


@pytest.mark.asyncio
async def test_failed_requires_failure_reason(db_session):
    from common.exceptions.base import BadRequestException

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    driver = await make_driver(db_session, team=team)
    leg = await make_leg(
        db_session, team=team, do=do, driver_id=driver.id,
        status=LegStatus.IN_TRANSIT,
    )
    await db_session.commit()

    svc = LegService(db_session, team.id)
    with pytest.raises(BadRequestException, match="failure_reason"):
        await svc.transition(leg.id, LegStatus.FAILED)


@pytest.mark.asyncio
async def test_invalid_transition_rejected(db_session):
    from common.exceptions.base import AppException

    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    leg = await make_leg(db_session, team=team, do=do)  # PENDING
    await db_session.commit()

    svc = LegService(db_session, team.id)
    # PENDING → COMPLETED 직접 차단
    with pytest.raises(AppException):
        await svc.transition(leg.id, LegStatus.COMPLETED)


@pytest.mark.asyncio
async def test_completed_settlement_idempotent(db_session):
    """이미 Settlement 있으면 중복 생성 안 함."""
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    driver = await make_driver(db_session, team=team)
    leg = await make_leg(
        db_session, team=team, do=do, driver_id=driver.id,
        status=LegStatus.IN_TRANSIT,
    )
    # 사전에 settlement 1개 미리 생성
    from tests.integration.factories import make_settlement
    pre = await make_settlement(db_session, team=team, leg=leg)
    await db_session.commit()

    svc = LegService(db_session, team.id)
    await svc.transition(leg.id, LegStatus.COMPLETED)

    rows = (await db_session.execute(
        select(SettlementModel).where(SettlementModel.leg_id == leg.id)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == pre.id
