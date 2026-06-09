# src/rate_multiplier/service.py
from __future__ import annotations
from decimal import Decimal
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from rate_multiplier.repository import RateMultiplierRepository
from rate_multiplier.schemas.request import RateMultiplierUpsertRequest
from rate_multiplier.schemas.response import (
    RateMultiplierResponseSchema, RateMultiplierDeleteResponseSchema,
)
from rate_sheet.const.status import RateContainerSize

# 컨플루언스 기본 배율 (등록된 row 없을 때 폴백)
_DEFAULT_FACTORS: dict[RateContainerSize, Decimal] = {
    RateContainerSize.SIZE_20: Decimal("0.85"),
    RateContainerSize.SIZE_40: Decimal("1.00"),
    RateContainerSize.SIZE_45: Decimal("1.00"),
}

_LABEL = "Rate Multiplier"


class RateMultiplierService:
    """컨테이너 배율 비즈니스 로직 + get_factor (정산 lookup 에서 사용)."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = RateMultiplierRepository(db, team_id)

    async def get_factor(
        self, container_size: RateContainerSize | None, rate_group_id: int | None = None
    ) -> Decimal:
        """배율 해석: 그룹 override → 팀 전역 → 컨플루언스 기본값. size None(Bobtail)이면 1.0."""
        if container_size is None:
            return Decimal("1.00")
        if rate_group_id is not None:
            row = await self.repo.find_scope(rate_group_id, container_size)
            if row is not None:
                return row.factor
        row = await self.repo.find_scope(None, container_size)
        if row is not None:
            return row.factor
        return _DEFAULT_FACTORS.get(container_size, Decimal("1.00"))

    async def upsert(
        self, payload: RateMultiplierUpsertRequest, actor_user_id: int | None = None
    ) -> RateMultiplierResponseSchema:
        existing = await self.repo.find_scope(payload.rate_group_id, payload.container_size)
        if existing is not None:
            row = await self.repo.update_row(
                existing, {"factor": payload.factor, "note": payload.note}, actor_user_id=actor_user_id,
            )
        else:
            row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return RateMultiplierResponseSchema.model_validate(row)

    async def list_all(
        self, rate_group_id: int | None = None, include_inactive: bool = False
    ) -> List[RateMultiplierResponseSchema]:
        rows = await self.repo.list_all(rate_group_id=rate_group_id, include_inactive=include_inactive)
        return [RateMultiplierResponseSchema.model_validate(r) for r in rows]

    async def delete(
        self, multiplier_id: int, actor_user_id: int | None = None
    ) -> RateMultiplierDeleteResponseSchema:
        row = await self.repo.get(multiplier_id)
        if not row:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(multiplier_id, actor_user_id=actor_user_id)
        return RateMultiplierDeleteResponseSchema(id=multiplier_id, deleted=True, soft_deleted=True)
