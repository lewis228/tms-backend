from __future__ import annotations
from typing import Optional, Sequence
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from common.repository.team_scoped import TeamScopedRepoMixin
from ocean.shipment.model import ShipmentModel


class ShipmentRepository(TeamScopedRepoMixin):
    """팀 scoped shipment 레포. ``team_id`` 는 생성자에서 받으며, 모든 쿼리의
    WHERE 첫 조건으로 강제된다. ``_require_team()`` 이 None 이면 즉시 ValueError.

    팀 경계 밖에서 호출해야 하는 시스템 배치(`SystemShipmentRepository`) 는
    아래에 별도 제공 — Celery Beat 가 전 팀의 next_scrape_at 을 스캔할 때 사용.
    """

    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db

    async def get_by_id(self, shipment_id: int) -> Optional[ShipmentModel]:
        stmt = (
            select(ShipmentModel)
            .options(
                selectinload(ShipmentModel.tags),
                selectinload(ShipmentModel.ref_numbers),
            )
            .where(
                ShipmentModel.team_id == self._require_team(),
                ShipmentModel.id == shipment_id,
                ShipmentModel.is_active.is_(True),
            )
        )
        return await self.db.scalar(stmt)

    async def get_by_id_with_relations(self, shipment_id: int) -> Optional[ShipmentModel]:
        stmt = (
            select(ShipmentModel)
            .options(
                selectinload(ShipmentModel.containers),
                selectinload(ShipmentModel.events),
                selectinload(ShipmentModel.tags),
                selectinload(ShipmentModel.ref_numbers),
            )
            .where(
                ShipmentModel.team_id == self._require_team(),
                ShipmentModel.id == shipment_id,
                ShipmentModel.is_active.is_(True),
            )
        )
        return await self.db.scalar(stmt)

    async def get_by_mbl(self, mbl: str) -> Optional[ShipmentModel]:
        stmt = (
            select(ShipmentModel)
            .options(
                selectinload(ShipmentModel.tags),
                selectinload(ShipmentModel.ref_numbers),
            )
            .where(
                ShipmentModel.team_id == self._require_team(),
                ShipmentModel.mbl == mbl,
                ShipmentModel.is_active.is_(True),
            )
        )
        return await self.db.scalar(stmt)

    async def get_by_mbl_with_relations(self, mbl: str) -> Optional[ShipmentModel]:
        stmt = (
            select(ShipmentModel)
            .options(
                selectinload(ShipmentModel.containers),
                selectinload(ShipmentModel.events),
                selectinload(ShipmentModel.tags),
                selectinload(ShipmentModel.ref_numbers),
            )
            .where(
                ShipmentModel.team_id == self._require_team(),
                ShipmentModel.mbl == mbl,
                ShipmentModel.is_active.is_(True),
            )
        )
        return await self.db.scalar(stmt)

    async def list_by_team(self) -> Sequence[ShipmentModel]:
        stmt = (
            select(ShipmentModel)
            .where(
                ShipmentModel.team_id == self._require_team(),
                ShipmentModel.is_active.is_(True),
            )
            .order_by(ShipmentModel.created_at.desc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def create(self, shipment: ShipmentModel) -> ShipmentModel:
        # team_id 가 mixin 으로 주입되므로 호출부는 팀 바인딩을 먼저 강제.
        shipment.team_id = self._require_team()
        self.db.add(shipment)
        await self.db.flush()
        await self.db.refresh(shipment)
        return shipment

    async def update_next_scrape_at(
        self, shipment_id: int, next_scrape_at: Optional[datetime]
    ) -> None:
        await self.db.execute(
            update(ShipmentModel)
            .where(
                ShipmentModel.team_id == self._require_team(),
                ShipmentModel.id == shipment_id,
            )
            .values(next_scrape_at=next_scrape_at)
        )
