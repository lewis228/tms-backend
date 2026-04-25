from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from ocean.scrape_log.repository import ScrapeLogRepository
from ocean.scrape_log.schemas.response import ScrapeLogResponseSchema


class ScrapeLogService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = ScrapeLogRepository(db, team_id)

    async def list_by_shipment(self, shipment_id: int) -> list[ScrapeLogResponseSchema]:
        logs = await self.repo.list_by_shipment(shipment_id)
        return [ScrapeLogResponseSchema.model_validate(l) for l in logs]
