# src/rate_quote/service.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_quote.repository import RateQuoteRepository
from rate_quote.schemas.request import (
    RateQuoteCreateRequest, RateQuoteUpdateRequest, PaginateRateQuoteRequest,
)
from rate_quote.schemas.response import RateQuoteResponseSchema


class RateQuoteService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = RateQuoteRepository(db, team_id)

    async def create(self, payload: RateQuoteCreateRequest, actor_user_id: int | None = None) -> RateQuoteResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return RateQuoteResponseSchema.model_validate(row)

    async def get(self, id_: int) -> RateQuoteResponseSchema:
        row = await self.repo.get(id_)
        if not row:
            raise NotFoundException("Rate Quote")
        return RateQuoteResponseSchema.model_validate(row)

    async def list_paginated(self, request: PaginateRateQuoteRequest) -> CursorPaginationResult[RateQuoteResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [RateQuoteResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(self, id_: int, payload: RateQuoteUpdateRequest, actor_user_id: int | None = None) -> RateQuoteResponseSchema:
        row = await self.repo.update(id_, payload.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("Rate Quote")
        return RateQuoteResponseSchema.model_validate(row)

    async def delete(self, id_: int, actor_user_id: int | None = None) -> bool:
        await self.repo.soft_deactivate_by_id(id_, actor_user_id=actor_user_id)
        return True
