"""Leg Repository."""
from __future__ import annotations

from app.core.repository import BaseRepository
from app.domains.legs.models import Leg


class LegRepository(BaseRepository[Leg]):
    model = Leg

    async def list_by_delivery_order(self, do_id: str) -> list[Leg]:
        stmt = self._base_query().where(Leg.delivery_order_id == do_id).order_by(
            Leg.created_at
        )
        return list((await self.db.execute(stmt)).scalars().all())
