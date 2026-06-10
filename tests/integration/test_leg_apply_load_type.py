# tests/integration/test_leg_apply_load_type.py
"""LegService.apply_load_type — Load Type 템플릿 → container leg 자동 생성 (재설계 1d)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from container.model import ContainerModel
from delivery_order.const.status import DeliveryStatus
from leg.const.status import LegStatus, MoveType, ServiceType, PointType, LegMoveCode
from leg.model import LegModel
from leg.service import LegService
from load_type_template.model import LoadTypeTemplateModel, LoadTypeTemplateStepModel
from load_type_template.const.status import (
    LoadDirection, TemplateLocationType as L, TemplateMoveType as M,
    TemplateServiceType as S, TemplateMoveCode as MC,
)

from tests.integration.factories import (
    make_customer, make_delivery_order, make_team, make_user,
)
from common.exceptions.base import BadRequestException


async def _make_container(db, team, do, *, seq=1):
    c = ContainerModel(team_id=team.id, delivery_order_id=do.id, sequence_no=seq)
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


async def _make_template(db, team):
    """Import Pre-pull (Live) 3-step 템플릿."""
    t = LoadTypeTemplateModel(
        team_id=team.id, code="IMP_PRE_L", name="Import Pre-pull (Live)",
        direction=LoadDirection.IMPORT, is_system=True,
    )
    db.add(t)
    await db.flush()
    steps = [
        LoadTypeTemplateStepModel(team_id=team.id, template_id=t.id, seq=1,
            from_location_type=L.TERMINAL, to_location_type=L.YARD,
            move_type=M.LOAD, service_type=S.DROP, move_code=MC.PPL),
        LoadTypeTemplateStepModel(team_id=team.id, template_id=t.id, seq=2,
            from_location_type=L.YARD, to_location_type=L.CUSTOMER,
            move_type=M.LOAD, service_type=S.LIVE, move_code=None),
        LoadTypeTemplateStepModel(team_id=team.id, template_id=t.id, seq=3,
            from_location_type=L.CUSTOMER, to_location_type=L.TERMINAL,
            move_type=M.EMPTY, service_type=S.LIVE, move_code=MC.PRE),
    ]
    db.add_all(steps)
    await db.flush()
    return t


@pytest.mark.asyncio
async def test_apply_load_type_generates_legs(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    container = await _make_container(db_session, team, do)
    template = await _make_template(db_session, team)
    user = await make_user(db_session)
    await db_session.commit()

    svc = LegService(db_session, team.id)
    created = await svc.apply_load_type(container.id, template.id, actor_user_id=user.id)

    assert len(created) == 3
    # 매핑 검증 — step1
    legs = (await db_session.execute(
        select(LegModel).where(LegModel.container_id == container.id, LegModel.is_active.is_(True))
        .order_by(LegModel.id.asc())
    )).scalars().all()
    assert [l.status for l in legs] == [LegStatus.PENDING] * 3
    assert legs[0].from_location_type == PointType.TERMINAL
    assert legs[0].to_location_type == PointType.YARD
    assert legs[0].move_type == MoveType.LOADED        # LOAD → LOADED
    assert legs[0].service_type == ServiceType.DROP
    assert legs[0].move_code == LegMoveCode.PPL
    assert legs[2].move_type == MoveType.EMPTY
    assert legs[2].move_code == LegMoveCode.PRE
    assert all(l.driver_id is None for l in legs)
    assert all(l.delivery_order_id == do.id for l in legs)

    # D/O 자동 DISPATCHING 파생 (미배차 leg)
    refreshed_do = (await db_session.execute(
        select(type(do)).where(type(do).id == do.id)
    )).scalar_one()
    assert refreshed_do.status == DeliveryStatus.DISPATCHING


@pytest.mark.asyncio
async def test_apply_load_type_blocks_when_existing(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    container = await _make_container(db_session, team, do)
    template = await _make_template(db_session, team)
    user = await make_user(db_session)
    await db_session.commit()

    svc = LegService(db_session, team.id)
    await svc.apply_load_type(container.id, template.id, actor_user_id=user.id)

    # replace_existing 없이 재호출 → 차단
    with pytest.raises(BadRequestException, match="replace_existing"):
        await svc.apply_load_type(container.id, template.id, actor_user_id=user.id)


@pytest.mark.asyncio
async def test_apply_load_type_replace_regenerates(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    container = await _make_container(db_session, team, do)
    template = await _make_template(db_session, team)
    user = await make_user(db_session)
    await db_session.commit()

    svc = LegService(db_session, team.id)
    await svc.apply_load_type(container.id, template.id, actor_user_id=user.id)
    again = await svc.apply_load_type(container.id, template.id, replace_existing=True, actor_user_id=user.id)

    assert len(again) == 3
    # 활성 leg 는 3개만 (옛 3개는 soft-delete)
    active = (await db_session.execute(
        select(LegModel).where(LegModel.container_id == container.id, LegModel.is_active.is_(True))
    )).scalars().all()
    assert len(active) == 3
