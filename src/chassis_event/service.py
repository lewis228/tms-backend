# src/chassis_event/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.pagination.schemas.pagination_response import CursorPaginationResult
from chassis_event.repository import ChassisEventRepository
from chassis_event.schemas.request import (
    ChassisEventCreateRequest, PaginateChassisEventRequest,
)
from chassis_event.schemas.response import ChassisEventResponseSchema


class ChassisEventService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = ChassisEventRepository(db, team_id)

    async def create(
        self, payload: ChassisEventCreateRequest, actor_user_id: int | None = None,
    ) -> ChassisEventResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return ChassisEventResponseSchema.model_validate(row)

    async def list_by_chassis(self, chassis_id: int) -> List[ChassisEventResponseSchema]:
        rows = await self.repo.list_by_chassis(chassis_id)
        return [ChassisEventResponseSchema.model_validate(r) for r in rows]

    async def list_paginated(
        self, request: PaginateChassisEventRequest,
    ) -> CursorPaginationResult[ChassisEventResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [ChassisEventResponseSchema.model_validate(r) for r in result.data]
        return result
