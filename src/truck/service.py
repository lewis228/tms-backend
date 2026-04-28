# src/truck/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from truck.repository import TruckRepository
from truck.schemas.request import (
    TruckCreateRequest, TruckUpdateRequest,
    PaginateTruckRequest, TruckBulkDeleteRequest,
)
from truck.schemas.response import (
    TruckResponseSchema, TruckDeleteResponseSchema,
    TruckBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class TruckService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = TruckRepository(db, team_id)

    async def create(
        self, payload: TruckCreateRequest, actor_user_id: int | None = None,
    ) -> TruckResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return TruckResponseSchema.model_validate(row)

    async def get(self, id_: int) -> TruckResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Truck")
        return TruckResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateTruckRequest,
    ) -> CursorPaginationResult[TruckResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [TruckResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: TruckUpdateRequest,
        actor_user_id: int | None = None,
    ) -> TruckResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Truck")
        return TruckResponseSchema.model_validate(row)

    async def delete(
        self, id_: int, actor_user_id: int | None = None,
    ) -> TruckDeleteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Truck")
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return TruckDeleteResponseSchema(id=id_, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: TruckBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> TruckBulkDeleteResponseSchema:
        existing = await self.repo.get_many(payload.ids)
        existing_ids = {r.id for r in existing}
        missing = set(payload.ids) - existing_ids
        if missing:
            raise NotFoundException(
                f"Truck(ID={list(missing)})", detail={"missing_ids": list(missing)},
            )
        results: List[BulkDeleteResultItem] = []
        for id_ in payload.ids:
            await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=id_, success=True, soft_deleted=True))
        return TruckBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
