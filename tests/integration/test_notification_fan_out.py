# tests/integration/test_notification_fan_out.py
"""notification.fan_out_event — 멤버 필터링 규칙 검증.

규칙:
- tenant 의 활성 멤버 (UserTenantModel.is_active=True) 만
- DRIVER role 제외
- actor 본인 제외
- 미지원 event_type 은 0 fan-out
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from notification.fan_out import fan_out_event
from notification.model import NotificationModel
from realtime.schemas.event import RealtimeEvent
from user.const.roles import RolesEnum

from tests.integration.factories import make_tenant, make_user, make_user_tenant


async def _setup_members(db_session, tenant):
    admin = await make_user(db_session, role=RolesEnum.ADMIN)
    dispatcher = await make_user(db_session, role=RolesEnum.DISPATCHER)
    driver = await make_user(db_session, role=RolesEnum.DRIVER)
    for u in (admin, dispatcher, driver):
        await make_user_tenant(db_session, user=u, tenant=tenant)
    await db_session.commit()
    return admin, dispatcher, driver


@pytest.mark.asyncio
async def test_fan_out_excludes_drivers(db_session):
    tenant = await make_tenant(db_session)
    admin, dispatcher, driver = await _setup_members(db_session, tenant)

    event = RealtimeEvent.now(
        type="do.status_changed",
        tenant_id=tenant.id,
        payload={"from": "PLANNING", "to": "DISPATCHED"},
    )
    n = await fan_out_event(db_session, event)
    await db_session.commit()

    assert n == 2  # admin + dispatcher

    rows = (await db_session.execute(
        select(NotificationModel.user_id).where(NotificationModel.tenant_id == tenant.id)
    )).scalars().all()
    assert set(rows) == {admin.id, dispatcher.id}


@pytest.mark.asyncio
async def test_fan_out_excludes_actor(db_session):
    tenant = await make_tenant(db_session)
    admin, dispatcher, _ = await _setup_members(db_session, tenant)

    event = RealtimeEvent.now(
        type="leg.created",
        tenant_id=tenant.id,
        actor_id=admin.id,
        payload={"deliveryOrderId": 42},
    )
    n = await fan_out_event(db_session, event)
    await db_session.commit()

    assert n == 1
    rows = (await db_session.execute(
        select(NotificationModel.user_id).where(NotificationModel.tenant_id == tenant.id)
    )).scalars().all()
    assert rows == [dispatcher.id]


@pytest.mark.asyncio
async def test_fan_out_unknown_event_type(db_session):
    tenant = await make_tenant(db_session)
    await _setup_members(db_session, tenant)

    event = RealtimeEvent.now(type="unknown.event", tenant_id=tenant.id)
    n = await fan_out_event(db_session, event)
    assert n == 0


@pytest.mark.asyncio
async def test_fan_out_inactive_membership_excluded(db_session):
    tenant = await make_tenant(db_session)
    admin, dispatcher, _ = await _setup_members(db_session, tenant)
    # dispatcher 의 membership 비활성화
    from tenant.model import UserTenantModel
    ut = (await db_session.execute(
        select(UserTenantModel).where(
            UserTenantModel.user_id == dispatcher.id,
            UserTenantModel.tenant_id == tenant.id,
        )
    )).scalar_one()
    ut.is_active = False
    await db_session.commit()

    event = RealtimeEvent.now(type="settlement.calculated", tenant_id=tenant.id)
    n = await fan_out_event(db_session, event)
    await db_session.commit()
    assert n == 1


@pytest.mark.asyncio
async def test_fan_out_other_tenant_isolated(db_session):
    a = await make_tenant(db_session)
    b = await make_tenant(db_session)
    await _setup_members(db_session, a)
    await _setup_members(db_session, b)

    event = RealtimeEvent.now(type="do.created", tenant_id=a.id, payload={"deliveryOrderId": 1})
    n = await fan_out_event(db_session, event)
    await db_session.commit()
    assert n == 2  # tenant a 의 admin + dispatcher 만
