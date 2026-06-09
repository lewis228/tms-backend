# tests/integration/test_notification_fan_out.py
"""notification.fan_out_event — 멤버 필터링 규칙 검증.

규칙:
- team 의 활성 멤버 (UserTeamModel.is_active=True) 만
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

from tests.integration.factories import make_team, make_user, make_user_team


async def _setup_members(db_session, team):
    admin = await make_user(db_session, role=RolesEnum.ADMIN)
    dispatcher = await make_user(db_session, role=RolesEnum.DISPATCHER)
    driver = await make_user(db_session, role=RolesEnum.DRIVER)
    for u in (admin, dispatcher, driver):
        await make_user_team(db_session, user=u, team=team)
    await db_session.commit()
    return admin, dispatcher, driver


@pytest.mark.asyncio
async def test_fan_out_excludes_drivers(db_session):
    team = await make_team(db_session)
    admin, dispatcher, driver = await _setup_members(db_session, team)

    event = RealtimeEvent.now(
        type="do.status_changed",
        team_id=team.id,
        payload={"from": "PLANNING", "to": "DISPATCHED"},
    )
    n = await fan_out_event(db_session, event)
    await db_session.commit()

    assert n == 2  # admin + dispatcher

    rows = (await db_session.execute(
        select(NotificationModel.user_id).where(NotificationModel.team_id == team.id)
    )).scalars().all()
    assert set(rows) == {admin.id, dispatcher.id}


@pytest.mark.asyncio
async def test_fan_out_excludes_actor(db_session):
    team = await make_team(db_session)
    admin, dispatcher, _ = await _setup_members(db_session, team)

    event = RealtimeEvent.now(
        type="leg.created",
        team_id=team.id,
        actor_id=admin.id,
        payload={"deliveryOrderId": 42},
    )
    n = await fan_out_event(db_session, event)
    await db_session.commit()

    assert n == 1
    rows = (await db_session.execute(
        select(NotificationModel.user_id).where(NotificationModel.team_id == team.id)
    )).scalars().all()
    assert rows == [dispatcher.id]


@pytest.mark.asyncio
async def test_fan_out_unknown_event_type(db_session):
    team = await make_team(db_session)
    await _setup_members(db_session, team)

    event = RealtimeEvent.now(type="unknown.event", team_id=team.id)
    n = await fan_out_event(db_session, event)
    assert n == 0


@pytest.mark.asyncio
async def test_fan_out_inactive_membership_excluded(db_session):
    team = await make_team(db_session)
    admin, dispatcher, _ = await _setup_members(db_session, team)
    # dispatcher 의 membership 비활성화
    from team.model import UserTeamModel
    ut = (await db_session.execute(
        select(UserTeamModel).where(
            UserTeamModel.user_id == dispatcher.id,
            UserTeamModel.team_id == team.id,
        )
    )).scalar_one()
    ut.is_active = False
    await db_session.commit()

    event = RealtimeEvent.now(type="leg.created", team_id=team.id)
    n = await fan_out_event(db_session, event)
    await db_session.commit()
    assert n == 1


@pytest.mark.asyncio
async def test_fan_out_other_team_isolated(db_session):
    a = await make_team(db_session)
    b = await make_team(db_session)
    await _setup_members(db_session, a)
    await _setup_members(db_session, b)

    event = RealtimeEvent.now(type="do.created", team_id=a.id, payload={"deliveryOrderId": 1})
    n = await fan_out_event(db_session, event)
    await db_session.commit()
    assert n == 2  # team a 의 admin + dispatcher 만
