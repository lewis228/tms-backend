# src/charge_code/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from charge_code.repository import ChargeCodeRepository
from charge_code.schemas.request import (
    ChargeCodeCreateRequest, ChargeCodeUpdateRequest,
    PaginateChargeCodeRequest, ChargeCodeBulkDeleteRequest,
)
from charge_code.schemas.response import (
    ChargeCodeResponseSchema, ChargeCodeDeleteResponseSchema,
    ChargeCodeBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class ChargeCodeService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = ChargeCodeRepository(db, team_id)

    async def create(
        self, payload: ChargeCodeCreateRequest, actor_user_id: int | None = None,
    ) -> ChargeCodeResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return ChargeCodeResponseSchema.model_validate(row)

    async def get(self, id_: int) -> ChargeCodeResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Charge Code")
        return ChargeCodeResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateChargeCodeRequest,
    ) -> CursorPaginationResult[ChargeCodeResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [ChargeCodeResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: ChargeCodeUpdateRequest,
        actor_user_id: int | None = None,
    ) -> ChargeCodeResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Charge Code")
        return ChargeCodeResponseSchema.model_validate(row)

    async def delete(
        self, id_: int, actor_user_id: int | None = None,
    ) -> ChargeCodeDeleteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Charge Code")
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return ChargeCodeDeleteResponseSchema(id=id_, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: ChargeCodeBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> ChargeCodeBulkDeleteResponseSchema:
        existing = await self.repo.get_many(payload.ids)
        existing_ids = {r.id for r in existing}
        missing = set(payload.ids) - existing_ids
        if missing:
            raise NotFoundException(
                f"Charge Code(ID={list(missing)})", detail={"missing_ids": list(missing)},
            )
        results: List[BulkDeleteResultItem] = []
        for id_ in payload.ids:
            await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=id_, success=True, soft_deleted=True))
        return ChargeCodeBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
