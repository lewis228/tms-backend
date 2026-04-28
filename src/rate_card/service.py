# src/rate_card/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_card.repository import RateCardRepository
from rate_card.schemas.request import (
    RateCardCreateRequest, RateCardUpdateRequest,
    PaginateRateCardRequest, RateCardBulkDeleteRequest,
)
from rate_card.schemas.response import (
    RateCardResponseSchema, RateCardDeleteResponseSchema,
    RateCardBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class RateCardService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = RateCardRepository(db, team_id)

    async def create(
        self, payload: RateCardCreateRequest, actor_user_id: int | None = None,
    ) -> RateCardResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return RateCardResponseSchema.model_validate(row)

    async def get(self, id_: int) -> RateCardResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Rate Card")
        return RateCardResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateRateCardRequest,
    ) -> CursorPaginationResult[RateCardResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [RateCardResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: RateCardUpdateRequest,
        actor_user_id: int | None = None,
    ) -> RateCardResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(id_, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Rate Card")
        return RateCardResponseSchema.model_validate(row)

    async def delete(
        self, id_: int, actor_user_id: int | None = None,
    ) -> RateCardDeleteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Rate Card")
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return RateCardDeleteResponseSchema(id=id_, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: RateCardBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> RateCardBulkDeleteResponseSchema:
        existing = await self.repo.get_many(payload.ids)
        existing_ids = {r.id for r in existing}
        missing = set(payload.ids) - existing_ids
        if missing:
            raise NotFoundException(
                f"Rate Card(ID={list(missing)})", detail={"missing_ids": list(missing)},
            )
        results: List[BulkDeleteResultItem] = []
        for id_ in payload.ids:
            await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=id_, success=True, soft_deleted=True))
        return RateCardBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
