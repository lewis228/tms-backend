"""Leg Repository."""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.pagination import PageParams
from app.core.repository import BaseRepository
from app.domains.legs.models import Leg


class LegRepository(BaseRepository[Leg]):
    model = Leg

    async def list_by_delivery_order(self, do_id: str) -> list[Leg]:
        stmt = self._base_query().where(Leg.delivery_order_id == do_id).order_by(
            Leg.created_at
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_by_driver(
        self, driver_id: str, params: PageParams
    ) -> tuple[list[Leg], int]:
        base = self._base_query().where(Leg.driver_id == driver_id)
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        stmt = base.order_by(Leg.created_at.desc()).offset(params.offset).limit(params.limit)
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, total
