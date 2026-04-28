# src/container/repository.py
from __future__ import annotations
from typing import Optional, List, Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from container.model import ContainerModel, ContainerEventModel
from container.schemas.request import (
    PaginateContainerRequest, PaginateContainerEventRequest,
)
from container.schemas.response import (
    ContainerResponseSchema, ContainerEventResponseSchema,
)


class ContainerRepository(TeamScopedRepoMixin):
    """Container 리포지토리. team scoped."""

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ── Create ─────────────────────────────────────────────

    async def create(
        self,
        payload: dict,
        actor_user_id: int | None = None,
    ) -> ContainerModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = ContainerModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def create_many(
        self,
        payloads: List[dict],
        actor_user_id: int | None = None,
    ) -> List[ContainerModel]:
        team_id = self._require_team()
        rows = []
        for payload in payloads:
            payload["team_id"] = team_id
            if actor_user_id is not None:
                payload["created_by_user_id"] = actor_user_id
            row = ContainerModel(**payload)
            self.db.add(row)
            rows.append(row)
        await self.db.flush()
        for row in rows:
            await self.db.refresh(row)
        return rows

    # ── Read ───────────────────────────────────────────────

    async def get(self, container_id: int) -> Optional[ContainerModel]:
        q = select(ContainerModel).where(
            ContainerModel.team_id == self._require_team(),
            ContainerModel.id == container_id,
            ContainerModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, ids: List[int]) -> List[ContainerModel]:
        if not ids:
            return []
        q = select(ContainerModel).where(
            ContainerModel.team_id == self._require_team(),
            ContainerModel.id.in_(ids),
            ContainerModel.is_active.is_(True),
        )
        return list((await self.db.execute(q)).scalars().all())

    async def list_by_delivery_order(self, delivery_order_id: int) -> List[ContainerModel]:
        """D/O 1건의 컨테이너 N개 (sequence_no 정렬)."""
        q = (
            select(ContainerModel)
            .where(
                ContainerModel.team_id == self._require_team(),
                ContainerModel.delivery_order_id == delivery_order_id,
                ContainerModel.is_active.is_(True),
            )
            .order_by(ContainerModel.sequence_no.asc(), ContainerModel.id.asc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def list_by_delivery_orders(self, do_ids: List[int]) -> List[ContainerModel]:
        """다수 D/O 의 컨테이너 한꺼번에."""
        if not do_ids:
            return []
        q = (
            select(ContainerModel)
            .where(
                ContainerModel.team_id == self._require_team(),
                ContainerModel.delivery_order_id.in_(do_ids),
                ContainerModel.is_active.is_(True),
            )
            .order_by(
                ContainerModel.delivery_order_id.asc(),
                ContainerModel.sequence_no.asc(),
                ContainerModel.id.asc(),
            )
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_paginated(self, request: PaginateContainerRequest) -> CursorPaginationResult[ContainerResponseSchema]:
        team_id = self._require_team()
        base_conditions = [ContainerModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(ContainerModel.is_active.is_(True))
        base_query = select(ContainerModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request, model=ContainerModel,
            session=self.db, base_query=base_query,
        )
        result.data = [ContainerResponseSchema.model_validate(r) for r in result.data]
        return result

    async def next_sequence_no(self, delivery_order_id: int) -> int:
        """해당 D/O 의 sequence_no 최댓값 + 1."""
        team_id = self._require_team()
        q = select(func.max(ContainerModel.sequence_no)).where(
            ContainerModel.team_id == team_id,
            ContainerModel.delivery_order_id == delivery_order_id,
        )
        result = await self.db.execute(q)
        max_seq = result.scalar()
        return (max_seq or 0) + 1

    # ── Update ──────────────────────────────────────────────

    async def update(
        self,
        container_id: int,
        payload: dict,
        actor_user_id: int | None = None,
    ) -> Optional[ContainerModel]:
        if not payload:
            return await self.get(container_id)
        q = select(ContainerModel).where(
            ContainerModel.team_id == self._require_team(),
            ContainerModel.id == container_id,
            ContainerModel.is_active.is_(True),
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
        if not row:
            return None
        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id", "delivery_order_id"}
        for k, v in payload.items():
            if k in protected:
                continue
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    # ── Delete ──────────────────────────────────────────────

    async def hard_delete_by_id(self, container_id: int) -> None:
        await self.db.execute(
            delete(ContainerModel).where(
                ContainerModel.team_id == self._require_team(),
                ContainerModel.id == container_id,
            )
        )
        await self.db.flush()

    async def soft_deactivate_by_id(
        self,
        container_id: int,
        actor_user_id: int | None = None,
    ) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(ContainerModel).where(
                ContainerModel.team_id == self._require_team(),
                ContainerModel.id == container_id,
                ContainerModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def get_existing_active_ids(self, ids: Iterable[int]) -> set[int]:
        id_list = list(ids)
        if not id_list:
            return set()
        stmt = select(ContainerModel.id).where(
            ContainerModel.team_id == self._require_team(),
            ContainerModel.is_active.is_(True),
            ContainerModel.id.in_(id_list),
        )
        return set((await self.db.execute(stmt)).scalars().all())

    # ═══════════════════════════════════════════════════════════════
    # Container Events
    # ═══════════════════════════════════════════════════════════════

    async def create_event(
        self,
        payload: dict,
        actor_user_id: int | None = None,
    ) -> ContainerEventModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = ContainerEventModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def list_events_by_container(self, container_id: int) -> List[ContainerEventModel]:
        q = (
            select(ContainerEventModel)
            .where(
                ContainerEventModel.team_id == self._require_team(),
                ContainerEventModel.container_id == container_id,
                ContainerEventModel.is_active.is_(True),
            )
            .order_by(ContainerEventModel.occurred_at.desc(), ContainerEventModel.id.desc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_events_paginated(
        self,
        request: PaginateContainerEventRequest,
    ) -> CursorPaginationResult[ContainerEventResponseSchema]:
        team_id = self._require_team()
        base_conditions = [ContainerEventModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(ContainerEventModel.is_active.is_(True))
        base_query = select(ContainerEventModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request, model=ContainerEventModel,
            session=self.db, base_query=base_query,
        )
        result.data = [ContainerEventResponseSchema.model_validate(r) for r in result.data]
        return result
