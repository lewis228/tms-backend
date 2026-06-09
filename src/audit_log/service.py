# src/audit_log/service.py
from __future__ import annotations
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from common.pagination.schemas.pagination_response import CursorPaginationResult
from audit_log.repository import AuditLogRepository
from audit_log.schemas.request import PaginateAuditLogRequest
from audit_log.schemas.response import AuditLogResponseSchema


class AuditLogService:
    """활동 타임라인 — 다른 도메인 service 가 record() 로 기록, 화면은 list 로 조회."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = AuditLogRepository(db, team_id)

    async def record(
        self, *, entity_type: str, entity_id: int, action: str,
        summary: str | None = None, before_state: dict | None = None,
        after_state: dict | None = None, actor_user_id: int | None = None,
    ) -> AuditLogResponseSchema:
        row = await self.repo.record({
            "entity_type": entity_type, "entity_id": entity_id, "action": action,
            "summary": summary, "before_state": before_state, "after_state": after_state,
        }, actor_user_id=actor_user_id)
        return AuditLogResponseSchema.model_validate(row)

    async def list_for_entity(self, entity_type: str, entity_id: int) -> List[AuditLogResponseSchema]:
        rows = await self.repo.list_for_entity(entity_type, entity_id)
        return [AuditLogResponseSchema.model_validate(r) for r in rows]

    async def list_recent(self, request: PaginateAuditLogRequest) -> CursorPaginationResult[AuditLogResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [AuditLogResponseSchema.model_validate(r) for r in result.data]
        return result
