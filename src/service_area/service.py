# src/service_area/service.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, AppException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from service_area.repository import ServiceAreaRepository
from service_area.schemas.request import ServiceAreaCreateRequest, PaginateServiceAreaRequest
from service_area.schemas.response import ServiceAreaResponseSchema, ServiceAreaDeleteResponseSchema

_LABEL = "Service Area"


class ServiceAreaService:
    """영업권역 선언 CRUD — 삭제는 소프트(is_active=False)."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = ServiceAreaRepository(db, team_id)

    async def create(
        self, payload: ServiceAreaCreateRequest, actor_user_id: int | None = None
    ) -> ServiceAreaResponseSchema:
        # uq(team,kind,state,value) 가 소프트삭제 행도 점유 → 있으면 되살림(revive)
        existing = await self.repo.get_duplicate(payload.kind, payload.state, payload.value)
        if existing is not None:
            if existing.is_active:
                raise AppException(
                    code="SERVICE_AREA_DUPLICATE",
                    message=f"이미 선언된 권역입니다: {payload.kind.value} {payload.state} {payload.value}",
                    status_code=409,
                )
            existing.is_active = True
            if actor_user_id is not None:
                existing.updated_by_user_id = actor_user_id
            await self.db.flush()
            await self.db.refresh(existing)
            return ServiceAreaResponseSchema.model_validate(existing)
        row = await self.repo.create(
            {"kind": payload.kind, "state": payload.state, "value": payload.value},
            actor_user_id=actor_user_id,
        )
        return ServiceAreaResponseSchema.model_validate(row)

    async def list_paginated(
        self, request: PaginateServiceAreaRequest
    ) -> CursorPaginationResult[ServiceAreaResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [ServiceAreaResponseSchema.model_validate(r) for r in result.data]
        return result

    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [ServiceAreaResponseSchema.model_validate(r) for r in result.items]
        return result

    async def delete(
        self, area_id: int, actor_user_id: int | None = None
    ) -> ServiceAreaDeleteResponseSchema:
        row = await self.repo.get(area_id)
        if not row:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(area_id, actor_user_id=actor_user_id)
        return ServiceAreaDeleteResponseSchema(id=area_id, deleted=True, soft_deleted=True)
