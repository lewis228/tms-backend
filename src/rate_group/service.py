# src/rate_group/service.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_group.repository import RateGroupRepository
from rate_group.schemas.request import (
    RateGroupCreateRequest, RateGroupUpdateRequest, PaginateRateGroupRequest,
)
from rate_group.schemas.response import (
    RateGroupResponseSchema, RateGroupDeleteResponseSchema,
)

_LABEL = "Rate Group"


class RateGroupService:
    """
    RateGroup(정산/요율 그룹) 비즈니스 로직.

    - method 별 기본 그룹(is_default)은 유일 — 새로 default 지정 시 같은 method 의 기존 default 해제.
    - 삭제는 항상 소프트(is_active=False).
    """
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = RateGroupRepository(db, team_id)

    # ── Create ──────────────────────────────────────────────────
    async def create(
        self, payload: RateGroupCreateRequest, actor_user_id: int | None = None
    ) -> RateGroupResponseSchema:
        data = payload.model_dump()
        if data.get("is_default"):
            await self.repo.clear_default_for_method(payload.method)
        row = await self.repo.create(data, actor_user_id=actor_user_id)
        return RateGroupResponseSchema.model_validate(row)

    # ── Read ────────────────────────────────────────────────────
    async def get(self, group_id: int) -> RateGroupResponseSchema:
        row = await self.repo.get(group_id)
        if not row:
            raise NotFoundException(_LABEL)
        return RateGroupResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateRateGroupRequest
    ) -> CursorPaginationResult[RateGroupResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [RateGroupResponseSchema.model_validate(r) for r in result.data]
        return result

    # ── Delta Sync ──────────────────────────────────────────────
    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [RateGroupResponseSchema.model_validate(r) for r in result.items]
        return result

    # ── Update ──────────────────────────────────────────────────
    async def update(
        self, group_id: int, payload: RateGroupUpdateRequest, actor_user_id: int | None = None
    ) -> RateGroupResponseSchema:
        existing = await self.repo.get(group_id)
        if not existing:
            raise NotFoundException(_LABEL)

        data = payload.model_dump(exclude_unset=True)
        # 기본 그룹 유일성: is_default=True 로 바꾸면 같은 method 의 다른 기본 그룹 해제
        if data.get("is_default") is True:
            method = data.get("method", existing.method)
            await self.repo.clear_default_for_method(method, exclude_id=group_id)

        row = await self.repo.update(group_id, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException(_LABEL)
        return RateGroupResponseSchema.model_validate(row)

    # ── Delete ──────────────────────────────────────────────────
    async def delete(
        self, group_id: int, actor_user_id: int | None = None
    ) -> RateGroupDeleteResponseSchema:
        row = await self.repo.get(group_id)
        if not row:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(group_id, actor_user_id=actor_user_id)
        return RateGroupDeleteResponseSchema(id=group_id, deleted=True, soft_deleted=True)
