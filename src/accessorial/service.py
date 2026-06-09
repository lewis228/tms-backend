# src/accessorial/service.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, ConflictException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from accessorial.repository import AccessorialRepository
from accessorial.schemas.request import (
    AccessorialCreateRequest, AccessorialUpdateRequest, PaginateAccessorialRequest,
)
from accessorial.schemas.response import (
    AccessorialResponseSchema, AccessorialDeleteResponseSchema,
)

_LABEL = "Accessorial"


class AccessorialService:
    """부가요금 규칙 마스터 + find_for_code (정산 snapshot 시 사용)."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = AccessorialRepository(db, team_id)

    async def create(self, payload: AccessorialCreateRequest, actor_user_id: int | None = None) -> AccessorialResponseSchema:
        dup = await self.repo.find_for_code(payload.code, payload.driver_id)
        if dup is not None and dup.driver_id == payload.driver_id:
            raise ConflictException(f"이미 존재하는 부가요금 코드: {payload.code} (driver={payload.driver_id})")
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return AccessorialResponseSchema.model_validate(row)

    async def get(self, acc_id: int) -> AccessorialResponseSchema:
        row = await self.repo.get(acc_id)
        if not row:
            raise NotFoundException(_LABEL)
        return AccessorialResponseSchema.model_validate(row)

    async def get_for_code(self, code: str, driver_id: int | None = None) -> AccessorialResponseSchema | None:
        row = await self.repo.find_for_code(code, driver_id)
        return AccessorialResponseSchema.model_validate(row) if row else None

    async def list_paginated(self, request: PaginateAccessorialRequest) -> CursorPaginationResult[AccessorialResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [AccessorialResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(self, acc_id: int, payload: AccessorialUpdateRequest, actor_user_id: int | None = None) -> AccessorialResponseSchema:
        row = await self.repo.update(acc_id, payload.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException(_LABEL)
        return AccessorialResponseSchema.model_validate(row)

    async def delete(self, acc_id: int, actor_user_id: int | None = None) -> AccessorialDeleteResponseSchema:
        row = await self.repo.get(acc_id)
        if not row:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(acc_id, actor_user_id=actor_user_id)
        return AccessorialDeleteResponseSchema(id=acc_id, deleted=True, soft_deleted=True)

    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [AccessorialResponseSchema.model_validate(r) for r in result.items]
        return result
