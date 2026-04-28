# src/equipment_pool/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from equipment_pool.repository import EquipmentPoolRepository
from equipment_pool.schemas.request import (
    EquipmentPoolCreateRequest, EquipmentPoolUpdateRequest,
    PaginateEquipmentPoolRequest, EquipmentPoolBulkDeleteRequest,
)
from equipment_pool.schemas.response import (
    EquipmentPoolResponseSchema, EquipmentPoolDeleteResponseSchema,
    EquipmentPoolBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class EquipmentPoolService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = EquipmentPoolRepository(db, team_id)

    async def create(
        self, payload: EquipmentPoolCreateRequest, actor_user_id: int | None = None,
    ) -> EquipmentPoolResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return EquipmentPoolResponseSchema.model_validate(row)

    async def get(self, id_: int) -> EquipmentPoolResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Equipment Pool")
        return EquipmentPoolResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateEquipmentPoolRequest,
    ) -> CursorPaginationResult[EquipmentPoolResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [EquipmentPoolResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: EquipmentPoolUpdateRequest,
        actor_user_id: int | None = None,
    ) -> EquipmentPoolResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Equipment Pool")
        return EquipmentPoolResponseSchema.model_validate(row)

    async def delete(
        self, id_: int, actor_user_id: int | None = None,
    ) -> EquipmentPoolDeleteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Equipment Pool")
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return EquipmentPoolDeleteResponseSchema(id=id_, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: EquipmentPoolBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> EquipmentPoolBulkDeleteResponseSchema:
        existing = await self.repo.get_many(payload.ids)
        existing_ids = {r.id for r in existing}
        missing = set(payload.ids) - existing_ids
        if missing:
            raise NotFoundException(
                f"Equipment Pool(ID={list(missing)})", detail={"missing_ids": list(missing)},
            )
        results: List[BulkDeleteResultItem] = []
        for id_ in payload.ids:
            await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=id_, success=True, soft_deleted=True))
        return EquipmentPoolBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
