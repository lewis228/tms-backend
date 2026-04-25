"""Driver 모바일 서비스.

DRIVER 사용자가 자기 데이터에만 접근. driver_id 는 user_id → drivers 조회로 결정.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.domains.driver.repository import DriverMobileRepository
from app.domains.drivers.models import Driver
from app.domains.legs.models import Leg
from app.domains.legs.repository import LegRepository
from app.domains.legs.service import LegService


class DriverMobileService:
    def __init__(
        self,
        repo: DriverMobileRepository,
        leg_repo: LegRepository,
        tenant_id: str,
    ) -> None:
        self.repo = repo
        self.leg_repo = leg_repo
        self.tenant_id = tenant_id

    async def resolve_driver_id(self, user_id: str) -> str:
        stmt = select(Driver).where(
            Driver.user_id == user_id,
            Driver.tenant_id == self.tenant_id,
            Driver.is_deleted.is_(False),
        )
        d = (await self.repo.db.execute(stmt)).scalar_one_or_none()
        if not d:
            raise NotFoundError("Driver profile not found for current user")
        return d.id

    async def today_legs(self, user_id: str) -> list[Leg]:
        driver_id = await self.resolve_driver_id(user_id)
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return await self.repo.today_legs(driver_id, start, end)

    async def checkpoint_leg(
        self,
        leg_id: str,
        target,
        *,
        user_id: str,
        failure_reason: str | None = None,
    ) -> Leg:
        # 본인 driver 의 leg 인지 검증
        driver_id = await self.resolve_driver_id(user_id)
        leg = await self.leg_repo.get_by_id(leg_id)
        if not leg or leg.driver_id != driver_id:
            raise NotFoundError("Leg not assigned to current driver")
        svc = LegService(self.leg_repo, self.tenant_id)
        return await svc.transition(leg_id, target, failure_reason=failure_reason)

    async def upsert_push_token(
        self, *, user_id: str, platform: str, token: str
    ):
        driver_id = await self.resolve_driver_id(user_id)
        row = await self.repo.upsert_token(
            driver_id=driver_id, platform=platform, token=token
        )
        await self.repo.db.commit()
        await self.repo.db.refresh(row)
        return row

    async def add_location_pings(
        self, *, user_id: str, pings: list[dict]
    ) -> int:
        driver_id = await self.resolve_driver_id(user_id)
        n = await self.repo.add_pings(driver_id=driver_id, pings=pings)
        await self.repo.db.commit()
        return n
