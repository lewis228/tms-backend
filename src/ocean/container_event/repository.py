from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.repository.team_scoped import TeamScopedRepoMixin
from ocean.container_event.model import ContainerEventModel


class ContainerEventRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db

    async def list_by_shipment(self, shipment_id: int) -> Sequence[ContainerEventModel]:
        stmt = (
            select(ContainerEventModel)
            .where(
                ContainerEventModel.team_id == self._require_team(),
                ContainerEventModel.shipment_id == shipment_id,
                ContainerEventModel.is_active.is_(True),
            )
            .order_by(ContainerEventModel.timestamp.desc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def list_by_container(self, container_id: int) -> Sequence[ContainerEventModel]:
        stmt = (
            select(ContainerEventModel)
            .where(
                ContainerEventModel.team_id == self._require_team(),
                ContainerEventModel.container_id == container_id,
                ContainerEventModel.is_active.is_(True),
            )
            .order_by(ContainerEventModel.timestamp.desc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def create(self, event: ContainerEventModel) -> ContainerEventModel:
        event.team_id = self._require_team()
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event
