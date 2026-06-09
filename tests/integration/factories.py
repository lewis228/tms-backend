# tests/integration/factories.py
"""Async-friendly 모델 팩토리 헬퍼.

factory-boy 의 SQLAlchemyModelFactory 는 sync session 가정이라 async 환경엔 안 맞음.
대신 명시적 async helper 로 작성 — 빠르고 디버깅 쉬움.

각 helper:
- 필요한 필드만 받고 안전한 default 적용
- db.add() + db.flush() 후 인스턴스 반환 (id 채워진 상태)
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from auth.const.providers import AuthProviderEnum
from customer.model import CustomerModel
from delivery_order.const.status import DeliveryStatus, ShipmentDirection
from delivery_order.model import DeliveryOrderModel
from driver.model import DriverModel
from leg.const.status import LegStatus, MoveType, ServiceType
from leg.model import LegModel
from location.const.kind import LocationKind
from location.model import LocationModel
from team.model import TeamModel, UserTeamModel
from terminal.model import TerminalModel
from user.const.roles import RolesEnum
from user.model import UserModel
from vessel.model import VesselModel


def _rand(prefix: str = "") -> str:
    return f"{prefix}{secrets.token_hex(4)}"


async def make_team(db: AsyncSession, *, name: str | None = None) -> TeamModel:
    t = TeamModel(name=name or _rand("team-"))
    db.add(t)
    await db.flush()
    return t


async def make_user(
    db: AsyncSession, *,
    role: RolesEnum = RolesEnum.DISPATCHER,
    email: str | None = None,
    name: str | None = None,
) -> UserModel:
    u = UserModel(
        email=email or f"{_rand()}@example.com",
        password="$2b$04$dummybcrypthashplaceholder1234567890abcdefghij",  # 60 chars
        auth_provider=AuthProviderEnum.EMAIL.value,
        role=role,
        name=name or _rand("user-"),
        # is_active_true 는 generated column (Computed) — 직접 지정 불가
    )
    db.add(u)
    await db.flush()
    return u


async def make_user_team(
    db: AsyncSession, *, user: UserModel, team: TeamModel,
    permission_group_id: int | None = None,
) -> UserTeamModel:
    ut = UserTeamModel(
        user_id=user.id,
        team_id=team.id,
        permission_group_id=permission_group_id,
    )
    db.add(ut)
    await db.flush()
    return ut


async def make_customer(
    db: AsyncSession, *, team: TeamModel, name: str | None = None,
) -> CustomerModel:
    c = CustomerModel(team_id=team.id, name=name or _rand("customer-"))
    db.add(c)
    await db.flush()
    return c


async def make_terminal(
    db: AsyncSession, *, team: TeamModel, name: str | None = None,
) -> TerminalModel:
    t = TerminalModel(team_id=team.id, name=name or _rand("terminal-"))
    db.add(t)
    await db.flush()
    return t


async def make_vessel(
    db: AsyncSession, *, team: TeamModel, name: str | None = None,
) -> VesselModel:
    v = VesselModel(team_id=team.id, name=name or _rand("vessel-"))
    db.add(v)
    await db.flush()
    return v


async def make_driver(
    db: AsyncSession, *, team: TeamModel, user: UserModel | None = None,
) -> DriverModel:
    if user is None:
        user = await make_user(db, role=RolesEnum.DRIVER)
    d = DriverModel(team_id=team.id, user_id=user.id)
    db.add(d)
    await db.flush()
    return d


async def make_location(
    db: AsyncSession, *, team: TeamModel,
    kind: LocationKind = LocationKind.YARD, name: str | None = None,
    customer_id: int | None = None,
) -> LocationModel:
    loc = LocationModel(
        team_id=team.id,
        name=name or _rand("location-"),
        kind=kind,
        customer_id=customer_id,
    )
    db.add(loc)
    await db.flush()
    return loc


async def make_delivery_order(
    db: AsyncSession, *, team: TeamModel, customer: CustomerModel,
    direction: ShipmentDirection = ShipmentDirection.IMPORT,
    status: DeliveryStatus = DeliveryStatus.PLANNING,
    **kw,
) -> DeliveryOrderModel:
    do = DeliveryOrderModel(
        team_id=team.id,
        customer_id=customer.id,
        direction=direction,
        status=status,
        **kw,
    )
    db.add(do)
    await db.flush()
    return do


async def make_leg(
    db: AsyncSession, *, team: TeamModel, do: DeliveryOrderModel,
    step: DeliveryStatus = DeliveryStatus.DISPATCHED,
    move_type: MoveType = MoveType.LOADED,
    service_type: ServiceType = ServiceType.LIVE,
    status: LegStatus = LegStatus.PENDING,
    driver_id: int | None = None,
    pickup_date: datetime | None = None,
    **kw,
) -> LegModel:
    leg = LegModel(
        team_id=team.id,
        delivery_order_id=do.id,
        step=step,
        move_type=move_type,
        service_type=service_type,
        status=status,
        driver_id=driver_id,
        pickup_date=pickup_date or datetime(2026, 5, 1, 9, tzinfo=timezone.utc),
        **kw,
    )
    db.add(leg)
    await db.flush()
    return leg


