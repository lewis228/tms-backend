from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from common.repository.team_scoped import TeamScopedRepoMixin
from ocean.ref_number.model import RefNumberModel


class RefNumberRepository(TeamScopedRepoMixin):
    """Shipment 자식 라인 — 외부 public CRUD 대신 ShipmentService 가 diff-upsert 로만 사용."""

    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db

    async def list_by_shipment(self, shipment_id: int) -> Sequence[RefNumberModel]:
        stmt = (
            select(RefNumberModel)
            .where(
                RefNumberModel.team_id == self._require_team(),
                RefNumberModel.shipment_id == shipment_id,
                RefNumberModel.is_active.is_(True),
            )
            .order_by(RefNumberModel.id.asc())
        )
        result = await self.db.scalars(stmt)
        return result.all()

    async def replace_for_shipment(
        self,
        shipment_id: int,
        values: Sequence[str],
        *,
        actor_user_id: int,
    ) -> None:
        """Shipment 의 ref_numbers 를 ``values`` 와 일치하도록 diff-upsert.

        현재 row 와 비교해 없어진 값은 **하드 delete** (tag M2M 과 달리 외부 FK
        참조가 없어서 보존 가치가 낮고, 동일 값 재입력 시 unique 제약 충돌 방지).
        새 값은 INSERT. 기존 값은 유지 (id / created_at 보존).
        """
        tid = self._require_team()
        existing_rows = await self.list_by_shipment(shipment_id)
        existing_values = {r.value for r in existing_rows}
        desired_values = {v for v in values if v}

        to_delete = existing_values - desired_values
        to_insert = desired_values - existing_values

        if to_delete:
            await self.db.execute(
                delete(RefNumberModel).where(
                    RefNumberModel.team_id == tid,
                    RefNumberModel.shipment_id == shipment_id,
                    RefNumberModel.value.in_(list(to_delete)),
                )
            )

        for val in to_insert:
            self.db.add(
                RefNumberModel(
                    team_id=tid,
                    shipment_id=shipment_id,
                    value=val,
                    created_by_user_id=actor_user_id,
                    updated_by_user_id=actor_user_id,
                )
            )
        await self.db.flush()

    async def delete_all_for_shipment(self, shipment_id: int) -> None:
        """Shipment hard-delete 시점에 FK CASCADE 로 자동 정리되지만, service 쪽
        명시적 정리(예: shipment soft-delete 시 정리) 가 필요할 때만 호출."""
        await self.db.execute(
            delete(RefNumberModel).where(
                RefNumberModel.team_id == self._require_team(),
                RefNumberModel.shipment_id == shipment_id,
            )
        )
        await self.db.flush()
