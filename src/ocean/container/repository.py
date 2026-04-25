from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from common.repository.team_scoped import TeamScopedRepoMixin
from ocean.container.model import ContainerModel
from ocean.shipment.model import ShipmentModel


class ContainerRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db

    async def get_by_id(self, container_id: int) -> Optional[ContainerModel]:
        stmt = (
            select(ContainerModel)
            .options(
                selectinload(ContainerModel.terminal_location),
                joinedload(ContainerModel.shipment).options(
                    selectinload(ShipmentModel.carrier),
                    selectinload(ShipmentModel.pol_location),
                    selectinload(ShipmentModel.pod_location),
                ),
            )
            .where(
                ContainerModel.team_id == self._require_team(),
                ContainerModel.id == container_id,
                ContainerModel.is_active.is_(True),
            )
        )
        return await self.db.scalar(stmt)

    async def get_by_number(self, number: str) -> Optional[ContainerModel]:
        stmt = select(ContainerModel).where(
            ContainerModel.team_id == self._require_team(),
            ContainerModel.number == number,
            ContainerModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)

    async def list_by_shipment(self, shipment_id: int) -> Sequence[ContainerModel]:
        stmt = (
            select(ContainerModel)
            .where(
                ContainerModel.team_id == self._require_team(),
                ContainerModel.shipment_id == shipment_id,
                ContainerModel.is_active.is_(True),
            )
            .order_by(ContainerModel.id.asc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    def base_list_query_with_shipment(self):
        """전역 containers 페이지용 base query. Shipment 조인 + 필요 nested 를
        eager-load. service 레이어가 필터 / 페이지네이션을 추가로 얹는다."""
        return (
            select(ContainerModel)
            .join(
                ShipmentModel,
                (ShipmentModel.id == ContainerModel.shipment_id)
                & (ShipmentModel.team_id == ContainerModel.team_id),
            )
            .options(
                joinedload(ContainerModel.shipment).options(
                    selectinload(ShipmentModel.carrier),
                    selectinload(ShipmentModel.pol_location),
                    selectinload(ShipmentModel.pod_location),
                ),
                selectinload(ContainerModel.terminal_location),
            )
            .where(
                ContainerModel.team_id == self._require_team(),
                ContainerModel.is_active.is_(True),
                ShipmentModel.is_active.is_(True),
            )
        )

    async def create(self, container: ContainerModel) -> ContainerModel:
        container.team_id = self._require_team()
        self.db.add(container)
        await self.db.flush()
        await self.db.refresh(container)
        return container
