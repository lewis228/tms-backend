# src/container/service.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, BadRequestException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from container.repository import ContainerRepository
from container.schemas.request import (
    ContainerCreateRequest, ContainerUpdateRequest,
    PaginateContainerRequest,
    ContainerEventCreateRequest, PaginateContainerEventRequest,
    ContainerBulkDeleteRequest,
)
from container.schemas.response import (
    ContainerResponseSchema, ContainerDeleteResponseSchema,
    ContainerEventResponseSchema,
    ContainerBulkDeleteResponseSchema, BulkDeleteResultItem, BulkSummary,
)


class ContainerService:
    """Container 비즈니스 로직."""

    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.repo = ContainerRepository(db, team_id)

    # ── Create ──

    async def create(
        self,
        payload: ContainerCreateRequest,
        actor_user_id: int | None = None,
    ) -> ContainerResponseSchema:
        data = payload.model_dump()
        if data.get("sequence_no") is None:
            data["sequence_no"] = await self.repo.next_sequence_no(data["delivery_order_id"])
        row = await self.repo.create(data, actor_user_id=actor_user_id)
        return ContainerResponseSchema.model_validate(row)

    # ── Read ──

    async def get(self, container_id: int) -> ContainerResponseSchema:
        row = await self.repo.get(container_id)
        if not row:
            raise NotFoundException("컨테이너")
        return ContainerResponseSchema.model_validate(row)

    async def list_by_delivery_order(self, delivery_order_id: int) -> List[ContainerResponseSchema]:
        rows = await self.repo.list_by_delivery_order(delivery_order_id)
        return [ContainerResponseSchema.model_validate(r) for r in rows]

    async def list_paginated(
        self, request: PaginateContainerRequest,
    ) -> CursorPaginationResult[ContainerResponseSchema]:
        result = await self.repo.get_paginated(request)
        result.data = [ContainerResponseSchema.model_validate(r) for r in result.data]
        return result

    # ── Update ──

    async def update(
        self,
        container_id: int,
        payload: ContainerUpdateRequest,
        actor_user_id: int | None = None,
    ) -> ContainerResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        row = await self.repo.update(container_id, data, actor_user_id=actor_user_id)
        if not row:
            raise NotFoundException("컨테이너")
        return ContainerResponseSchema.model_validate(row)

    # ── Delete ──

    async def delete(
        self,
        container_id: int,
        actor_user_id: int | None = None,
    ) -> ContainerDeleteResponseSchema:
        row = await self.repo.get(container_id)
        if not row:
            raise NotFoundException("컨테이너")
        await self.repo.soft_deactivate_by_id(container_id, actor_user_id=actor_user_id)
        return ContainerDeleteResponseSchema(id=container_id, deleted=True, soft_deleted=True)

    async def delete_bulk(
        self,
        payload: ContainerBulkDeleteRequest,
        actor_user_id: int | None = None,
    ) -> ContainerBulkDeleteResponseSchema:
        existing_rows = await self.repo.get_many(payload.ids)
        existing_ids = {row.id for row in existing_rows}
        missing_ids = set(payload.ids) - existing_ids
        if missing_ids:
            raise NotFoundException(
                f"컨테이너(ID={list(missing_ids)})",
                detail={"missing_ids": list(missing_ids)},
            )
        results: List[BulkDeleteResultItem] = []
        for cid in payload.ids:
            await self.repo.soft_deactivate_by_id(cid, actor_user_id=actor_user_id)
            results.append(BulkDeleteResultItem(id=cid, success=True, soft_deleted=True))
        return ContainerBulkDeleteResponseSchema(
            results=results,
            summary=BulkSummary(total=len(payload.ids), succeeded=len(results), failed=0),
        )

    # ═══════════════════════════════════════════════════════════════
    # Container Events
    # ═══════════════════════════════════════════════════════════════

    async def create_event(
        self,
        container_id: int,
        payload: ContainerEventCreateRequest,
        actor_user_id: int | None = None,
    ) -> ContainerEventResponseSchema:
        # 컨테이너 존재 검증
        container = await self.repo.get(container_id)
        if not container:
            raise NotFoundException("컨테이너")
        data = payload.model_dump()
        data["container_id"] = container_id
        row = await self.repo.create_event(data, actor_user_id=actor_user_id)
        return ContainerEventResponseSchema.model_validate(row)

    async def list_events_by_container(self, container_id: int) -> List[ContainerEventResponseSchema]:
        return [
            ContainerEventResponseSchema.model_validate(r)
            for r in await self.repo.list_events_by_container(container_id)
        ]

    async def list_events_paginated(
        self, request: PaginateContainerEventRequest,
    ) -> CursorPaginationResult[ContainerEventResponseSchema]:
        result = await self.repo.get_events_paginated(request)
        result.data = [ContainerEventResponseSchema.model_validate(r) for r in result.data]
        return result
