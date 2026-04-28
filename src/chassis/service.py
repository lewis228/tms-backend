# src/chassis/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from chassis.repository import ChassisRepository
from chassis.schemas.request import (
    ChassisCreateRequest, ChassisUpdateRequest,
    PaginateChassisRequest, ChassisBulkDeleteRequest,
)
from chassis.schemas.response import (
    ChassisResponseSchema, ChassisDeleteResponseSchema,
    ChassisBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class ChassisService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = ChassisRepository(db, team_id)

    async def create(
        self, payload: ChassisCreateRequest, actor_user_id: int | None = None,
    ) -> ChassisResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return ChassisResponseSchema.model_validate(row)

    async def get(self, id_: int) -> ChassisResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Chassis")
        return ChassisResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateChassisRequest,
    ) -> CursorPaginationResult[ChassisResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [ChassisResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: ChassisUpdateRequest,
        actor_user_id: int | None = None,
    ) -> ChassisResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Chassis")
        return ChassisResponseSchema.model_validate(row)

    async def delete(
        self, id_: int, actor_user_id: int | None = None,
    ) -> ChassisDeleteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Chassis")
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return ChassisDeleteResponseSchema(id=id_, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: ChassisBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> ChassisBulkDeleteResponseSchema:
        existing = await self.repo.get_many(payload.ids)
        existing_ids = {r.id for r in existing}
        missing = set(payload.ids) - existing_ids
        if missing:
            raise NotFoundException(
                f"Chassis(ID={list(missing)})", detail={"missing_ids": list(missing)},
            )
        results: List[BulkDeleteResultItem] = []
        for id_ in payload.ids:
            await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=id_, success=True, soft_deleted=True))
        return ChassisBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
