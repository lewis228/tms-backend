# src/leg_charge/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from leg_charge.repository import LegChargeRepository
from leg_charge.auto_match import auto_match_for_leg
from leg_charge.schemas.request import (
    LegChargeCreateRequest, LegChargeUpdateRequest,
    PaginateLegChargeRequest, LegChargeBulkDeleteRequest,
)
from leg_charge.schemas.response import (
    LegChargeResponseSchema, LegChargeDeleteResponseSchema,
    LegChargeBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class LegChargeService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = LegChargeRepository(db, team_id)

    async def auto_match(
        self, leg_id: int, actor_user_id: int | None = None,
    ) -> list[LegChargeResponseSchema]:
        rows = await auto_match_for_leg(self.db, self.team_id, leg_id, actor_user_id)
        return [LegChargeResponseSchema.model_validate(r) for r in rows]

    async def create(
        self, payload: LegChargeCreateRequest, actor_user_id: int | None = None,
    ) -> LegChargeResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return LegChargeResponseSchema.model_validate(row)

    async def get(self, id_: int) -> LegChargeResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Leg Charge")
        return LegChargeResponseSchema.model_validate(row)

    async def list_by_leg(self, leg_id: int) -> List[LegChargeResponseSchema]:
        rows = await self.repo.list_by_leg(leg_id)
        return [LegChargeResponseSchema.model_validate(r) for r in rows]

    async def list_paginated(
        self, request: PaginateLegChargeRequest,
    ) -> CursorPaginationResult[LegChargeResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [LegChargeResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: LegChargeUpdateRequest,
        actor_user_id: int | None = None,
    ) -> LegChargeResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Leg Charge")
        return LegChargeResponseSchema.model_validate(row)

    async def delete(
        self, id_: int, actor_user_id: int | None = None,
    ) -> LegChargeDeleteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Leg Charge")
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return LegChargeDeleteResponseSchema(id=id_, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: LegChargeBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> LegChargeBulkDeleteResponseSchema:
        existing = await self.repo.get_many(payload.ids)
        existing_ids = {r.id for r in existing}
        missing = set(payload.ids) - existing_ids
        if missing:
            raise NotFoundException(
                f"Leg Charge(ID={list(missing)})", detail={"missing_ids": list(missing)},
            )
        results: List[BulkDeleteResultItem] = []
        for id_ in payload.ids:
            await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=id_, success=True, soft_deleted=True))
        return LegChargeBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
