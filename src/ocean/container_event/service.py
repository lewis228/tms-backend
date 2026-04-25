from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from ocean.container_event.repository import ContainerEventRepository
from ocean.container_event.schemas.response import ContainerEventResponseSchema


class ContainerEventService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = ContainerEventRepository(db, team_id)

    async def list_by_shipment(self, shipment_id: int) -> list[ContainerEventResponseSchema]:
        events = await self.repo.list_by_shipment(shipment_id)
        return [ContainerEventResponseSchema.model_validate(e) for e in events]
