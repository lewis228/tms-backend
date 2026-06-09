# src/rate_point/service.py
from __future__ import annotations
from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_point.repository import RatePointRepository
from rate_point.schemas.request import (
    RatePointCreateRequest, RatePointUpdateRequest, PaginateRatePointRequest,
    RatePointBulkCreateRequest, RatePointBulkUpdateRequest, RatePointBulkDeleteRequest,
)
from rate_point.schemas.response import (
    RatePointResponseSchema, RatePointDeleteResponseSchema,
    RatePointBulkCreateResponseSchema, RatePointBulkUpdateResponseSchema, RatePointBulkDeleteResponseSchema,
    BulkResultItem, BulkDeleteResultItem, BulkSummary,
)

_LABEL = "Rate Point"


class RatePointService:
    """
    RatePoint(요율표 행: Terminal/Yard) 비즈니스 로직.

    삭제 정책: 항상 소프트 삭제 (is_active=False) — 과거 Rate Sheet/Invoice 이력 보존.
    벌크 작업: 사전 검증 실패 → 전체 실패 (트랜잭션 롤백).
    """
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = RatePointRepository(db, team_id)

    # ── Create ──────────────────────────────────────────────────
    async def create(
        self, payload: RatePointCreateRequest, actor_user_id: int | None = None
    ) -> RatePointResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        return RatePointResponseSchema.model_validate(row)

    async def create_bulk(
        self, payload: RatePointBulkCreateRequest, actor_user_id: int | None = None
    ) -> RatePointBulkCreateResponseSchema:
        results: List[BulkResultItem] = []
        for item in payload.items:
            row = await self.repo.create(item.model_dump(), actor_user_id=actor_user_id)
            point = RatePointResponseSchema.model_validate(row)
            results.append(BulkResultItem(id=point.id, success=True, data=point))
        return RatePointBulkCreateResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.items), succeeded=len(results), failed=0),
        )

    # ── Read ────────────────────────────────────────────────────
    async def get(self, point_id: int) -> RatePointResponseSchema:
        row = await self.repo.get(point_id)
        if not row:
            raise NotFoundException(_LABEL)
        return RatePointResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateRatePointRequest
    ) -> CursorPaginationResult[RatePointResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [RatePointResponseSchema.model_validate(r) for r in result.data]
        return result

    # ── Delta Sync ──────────────────────────────────────────────
    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [RatePointResponseSchema.model_validate(r) for r in result.items]
        return result

    # ── Update ──────────────────────────────────────────────────
    async def update(
        self, point_id: int, payload: RatePointUpdateRequest, actor_user_id: int | None = None
    ) -> RatePointResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(point_id, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException(_LABEL)
        return RatePointResponseSchema.model_validate(row)

    async def update_bulk(
        self, payload: RatePointBulkUpdateRequest, actor_user_id: int | None = None
    ) -> RatePointBulkUpdateResponseSchema:
        request_ids = [item.id for item in payload.items]
        existing_rows = await self.repo.get_many(request_ids)
        existing_ids = {row.id for row in existing_rows}
        missing_ids = set(request_ids) - existing_ids
        if missing_ids:
            raise NotFoundException(
                f"{_LABEL}(ID={list(missing_ids)})",
                detail={"missing_ids": list(missing_ids)},
            )

        results: List[BulkResultItem] = []
        for item in payload.items:
            data = item.model_dump(exclude_unset=True)
            data.pop('id', None)
            row = await self.repo.update(item.id, data, actor_user_id=actor_user_id)
            point = RatePointResponseSchema.model_validate(row)
            results.append(BulkResultItem(id=point.id, success=True, data=point))
        return RatePointBulkUpdateResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.items), succeeded=len(results), failed=0),
        )

    # ── Delete ──────────────────────────────────────────────────
    async def delete(
        self, point_id: int, actor_user_id: int | None = None
    ) -> RatePointDeleteResponseSchema:
        row = await self.repo.get(point_id)
        if not row:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(point_id, actor_user_id=actor_user_id)
        return RatePointDeleteResponseSchema(id=point_id, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self, payload: RatePointBulkDeleteRequest, actor_user_id: int | None = None
    ) -> RatePointBulkDeleteResponseSchema:
        existing_rows = await self.repo.get_many(payload.ids)
        existing_ids = {row.id for row in existing_rows}
        missing_ids = set(payload.ids) - existing_ids
        if missing_ids:
            raise NotFoundException(
                f"{_LABEL}(ID={list(missing_ids)})",
                detail={"missing_ids": list(missing_ids)},
            )

        results: List[BulkDeleteResultItem] = []
        for point_id in payload.ids:
            await self.repo.soft_deactivate_by_id(point_id, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=point_id, success=True, soft_deleted=True))
        return RatePointBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )
