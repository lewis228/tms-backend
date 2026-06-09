# tests/integration/test_do_hold_cancel.py
"""D/O Hold/Cancel overlay + 활동 타임라인(audit) + 만료 알림 (Phase 6)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from delivery_order.const.status import DeliveryStatus
from delivery_order.model import DeliveryOrderModel
from delivery_order.service import DeliveryOrderService
from delivery_order.state_derive import derive_do_dispatch_state
from leg.const.status import LegStatus
from truck.model import TruckModel
from truck.const.status import TruckOwnerKind, TruckStatus
from analytics.service import AnalyticsService
from audit_log.service import AuditLogService

from tests.integration.factories import (
    make_customer, make_delivery_order, make_leg, make_team, make_user,
)


@pytest.mark.asyncio
async def test_hold_pauses_auto_derive(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer,
                                   status=DeliveryStatus.PLANNING)
    user = await make_user(db_session)
    await db_session.commit()

    svc = DeliveryOrderService(db_session, team.id)
    held = await svc.set_hold(do.id, on_hold=True, reason="서류 보류", actor_user_id=user.id)
    assert held.is_on_hold is True
    assert held.hold_reason == "서류 보류"

    # Hold 중엔 leg 생겨도 자동 파생(DISPATCHING) 안 됨
    await make_leg(db_session, team=team, do=do, status=LegStatus.PENDING)
    await db_session.commit()
    res = await derive_do_dispatch_state(db_session, team.id, do.id)
    assert res is None
    refreshed = (await db_session.execute(
        select(DeliveryOrderModel).where(DeliveryOrderModel.id == do.id)
    )).scalar_one()
    assert refreshed.status == DeliveryStatus.PLANNING

    # 활동 타임라인에 hold 기록
    activity = await AuditLogService(db_session, team.id).list_for_entity("delivery_order", do.id)
    assert any(a.action == "hold_set" for a in activity)


@pytest.mark.asyncio
async def test_cancel_sets_timestamp_and_clears_hold(db_session):
    team = await make_team(db_session)
    customer = await make_customer(db_session, team=team)
    do = await make_delivery_order(db_session, team=team, customer=customer)
    user = await make_user(db_session)
    await db_session.commit()

    svc = DeliveryOrderService(db_session, team.id)
    await svc.set_hold(do.id, on_hold=True, reason="x", actor_user_id=user.id)
    cancelled = await svc.cancel(do.id, reason="고객 취소", actor_user_id=user.id)
    assert cancelled.cancelled_at is not None
    assert cancelled.is_on_hold is False
    assert cancelled.cancel_reason == "고객 취소"


@pytest.mark.asyncio
async def test_expiring_compliance(db_session):
    team = await make_team(db_session)
    await make_user(db_session)
    soon = date.today() + timedelta(days=10)
    far = date.today() + timedelta(days=200)
    db_session.add(TruckModel(team_id=team.id, plate_no="EXP-1",
                              owner_kind=TruckOwnerKind.COMPANY, status=TruckStatus.ACTIVE,
                              insurance_expires_at=soon, registration_expires_at=far))
    await db_session.commit()

    resp = await AnalyticsService(db_session, team.id).expiring_compliance(days=30)
    fields = {(i.entity_type, i.field) for i in resp.items}
    assert ("truck", "insurance") in fields       # 10일 → 포함
    assert ("truck", "registration") not in fields  # 200일 → 제외
    assert resp.soon_count >= 1
