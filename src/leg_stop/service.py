# src/leg_stop/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from leg_stop.repository import LegStopRepository
from leg_stop.schemas.request import (
    LegStopCreateRequest, LegStopUpdateRequest,
    PaginateLegStopRequest, LegStopBulkDeleteRequest,
)
from leg_stop.schemas.response import (
    LegStopResponseSchema, LegStopDeleteResponseSchema,
    LegStopBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class LegStopService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = LegStopRepository(db, team_id)

    async def create(
        self, payload: LegStopCreateRequest, actor_user_id: int | None = None,
    ) -> LegStopResponseSchema:
        data = payload.model_dump()
        # sequence_no 자동 보정 (0 이거나 누락 시)
        if not data.get("sequence_no"):
            data["sequence_no"] = await self.repo.next_sequence_no(data["leg_id"])
        row = await self.repo.create(data, actor_user_id=actor_user_id)
        return LegStopResponseSchema.model_validate(row)

    async def get(self, id_: int) -> LegStopResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Leg Stop")
        return LegStopResponseSchema.model_validate(row)

    async def list_by_leg(self, leg_id: int) -> List[LegStopResponseSchema]:
        rows = await self.repo.list_by_leg(leg_id)
        return [LegStopResponseSchema.model_validate(r) for r in rows]

    async def list_paginated(
        self, request: PaginateLegStopRequest,
    ) -> CursorPaginationResult[LegStopResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [LegStopResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: LegStopUpdateRequest,
        actor_user_id: int | None = None,
    ) -> LegStopResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Leg Stop")
        return LegStopResponseSchema.model_validate(row)

    async def delete(
        self, id_: int, actor_user_id: int | None = None,
    ) -> LegStopDeleteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Leg Stop")
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return LegStopDeleteResponseSchema(id=id_, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: LegStopBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> LegStopBulkDeleteResponseSchema:
        existing = await self.repo.get_many(payload.ids)
        existing_ids = {r.id for r in existing}
        missing = set(payload.ids) - existing_ids
        if missing:
            raise NotFoundException(
                f"Leg Stop(ID={list(missing)})", detail={"missing_ids": list(missing)},
            )
        results: List[BulkDeleteResultItem] = []
        for id_ in payload.ids:
            await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=id_, success=True, soft_deleted=True))
        return LegStopBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
