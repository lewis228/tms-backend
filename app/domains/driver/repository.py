"""Driver 모바일 Repository (PushToken / LocationPing)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.driver.models import DriverLocationPing, DriverPushToken
from app.domains.legs.models import Leg
from app.models.enums import LegStatus


class DriverMobileRepository:
    def __init__(self, db: AsyncSession, *, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def today_legs(self, driver_id: str, today_start, today_end) -> list[Leg]:
        stmt = (
            select(Leg)
            .where(
                Leg.tenant_id == self.tenant_id,
                Leg.is_deleted.is_(False),
                Leg.driver_id == driver_id,
                Leg.status.in_([LegStatus.PENDING, LegStatus.IN_TRANSIT]),
            )
            .order_by(
                case((Leg.pickup_date.is_(None), 1), else_=0),
                Leg.pickup_date.asc(),
                Leg.created_at.asc(),
            )
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_token(self, token: str) -> DriverPushToken | None:
        stmt = select(DriverPushToken).where(
            DriverPushToken.token == token,
            DriverPushToken.tenant_id == self.tenant_id,
            DriverPushToken.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def upsert_token(
        self, *, driver_id: str, platform: str, token: str
    ) -> DriverPushToken:
        existing = await self.get_token(token)
        now = datetime.now(timezone.utc)
        if existing:
            existing.driver_id = driver_id
            existing.platform = platform
            existing.last_used_at = now
            await self.db.flush()
            return existing
        row = DriverPushToken(
            tenant_id=self.tenant_id,
            driver_id=driver_id,
            platform=platform,
            token=token,
            last_used_at=now,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def add_pings(
        self, *, driver_id: str, pings: list[dict]
    ) -> int:
        rows = [
            DriverLocationPing(
                tenant_id=self.tenant_id,
                driver_id=driver_id,
                **p,
            )
            for p in pings
        ]
        self.db.add_all(rows)
        await self.db.flush()
        return len(rows)
