from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.repository.team_scoped import TeamScopedRepoMixin
from ocean.scrape_log.model import ScrapeLogModel


class ScrapeLogRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db

    async def list_by_shipment(self, shipment_id: int) -> Sequence[ScrapeLogModel]:
        stmt = (
            select(ScrapeLogModel)
            .where(
                ScrapeLogModel.team_id == self._require_team(),
                ScrapeLogModel.shipment_id == shipment_id,
                ScrapeLogModel.is_active.is_(True),
            )
            .order_by(ScrapeLogModel.scraped_at.desc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def create(self, log: ScrapeLogModel) -> ScrapeLogModel:
        log.team_id = self._require_team()
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        return log
