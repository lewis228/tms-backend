# src/driver_rate_assignment/service.py
from __future__ import annotations
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from realtime.emit import emit_entity_event
from driver_rate_assignment.repository import DriverRateAssignmentRepository
from driver_rate_assignment.schemas.request import (
    DriverRateAssignmentCreateRequest, DriverRateAssignmentUpdateRequest,
    PaginateDriverRateAssignmentRequest,
)
from driver_rate_assignment.schemas.response import (
    DriverRateAssignmentResponseSchema, DriverRateAssignmentDeleteResponseSchema,
)

_LABEL = "Driver Rate Assignment"


class DriverRateAssignmentService:
    """
    DriverRateAssignment(드라이버↔요율그룹 배정) 비즈니스 로직.

    - 유효일자 기반: work_date 에 유효한 배정으로 요율그룹을 해석(정산 lookup 의 진입점).
    - 삭제는 항상 소프트(is_active=False).
    """
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = DriverRateAssignmentRepository(db, team_id)

    # ── Create ──────────────────────────────────────────────────
    async def create(
        self, payload: DriverRateAssignmentCreateRequest, actor_user_id: int | None = None
    ) -> DriverRateAssignmentResponseSchema:
        row = await self.repo.create(payload.model_dump(), actor_user_id=actor_user_id)
        await emit_entity_event("driver_rate_assignment.created", self.team_id,
                                {"assignmentId": row.id, "driverId": row.driver_id}, actor_user_id)
        return DriverRateAssignmentResponseSchema.model_validate(row)

    # ── Read ────────────────────────────────────────────────────
    async def get(self, assignment_id: int) -> DriverRateAssignmentResponseSchema:
        row = await self.repo.get(assignment_id)
        if not row:
            raise NotFoundException(_LABEL)
        return DriverRateAssignmentResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateDriverRateAssignmentRequest
    ) -> CursorPaginationResult[DriverRateAssignmentResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [DriverRateAssignmentResponseSchema.model_validate(r) for r in result.data]
        return result

    async def get_active_for_driver(
        self, driver_id: int, work_date: date
    ) -> DriverRateAssignmentResponseSchema | None:
        """work_date 기준 유효 배정 (없으면 None) — 정산 lookup 진입점."""
        row = await self.repo.get_active_for_driver(driver_id, work_date)
        if not row:
            return None
        return DriverRateAssignmentResponseSchema.model_validate(row)

    # ── Delta Sync ──────────────────────────────────────────────
    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [DriverRateAssignmentResponseSchema.model_validate(r) for r in result.items]
        return result

    # ── Update ──────────────────────────────────────────────────
    async def update(
        self, assignment_id: int, payload: DriverRateAssignmentUpdateRequest,
        actor_user_id: int | None = None,
    ) -> DriverRateAssignmentResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(assignment_id, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException(_LABEL)
        await emit_entity_event("driver_rate_assignment.updated", self.team_id,
                                {"assignmentId": assignment_id, "driverId": row.driver_id}, actor_user_id)
        return DriverRateAssignmentResponseSchema.model_validate(row)

    # ── Delete ──────────────────────────────────────────────────
    async def delete(
        self, assignment_id: int, actor_user_id: int | None = None
    ) -> DriverRateAssignmentDeleteResponseSchema:
        row = await self.repo.get(assignment_id)
        if not row:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(assignment_id, actor_user_id=actor_user_id)
        await emit_entity_event("driver_rate_assignment.deleted", self.team_id,
                                {"assignmentId": assignment_id, "driverId": row.driver_id}, actor_user_id)
        return DriverRateAssignmentDeleteResponseSchema(id=assignment_id, deleted=True, soft_deleted=True)
