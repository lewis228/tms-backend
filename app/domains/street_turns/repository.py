"""StreetTurn Repository."""
from __future__ import annotations

from sqlalchemy import or_, select

from app.core.repository import BaseRepository
from app.domains.street_turns.models import StreetTurn


class StreetTurnRepository(BaseRepository[StreetTurn]):
    model = StreetTurn

    async def find_by_order(self, order_id: str) -> StreetTurn | None:
        stmt = self._base_query().where(
            or_(StreetTurn.import_order_id == order_id, StreetTurn.export_order_id == order_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
