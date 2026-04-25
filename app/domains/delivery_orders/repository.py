"""DeliveryOrder Repository."""
from __future__ import annotations

from app.core.repository import BaseRepository
from app.domains.delivery_orders.models import DeliveryOrder


class DeliveryOrderRepository(BaseRepository[DeliveryOrder]):
    model = DeliveryOrder

    async def get_by_container(self, container_number: str) -> list[DeliveryOrder]:
        stmt = self._base_query().where(DeliveryOrder.container_number == container_number)
        return list((await self.db.execute(stmt)).scalars().all())
