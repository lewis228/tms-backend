# src/rate_group/repository.py
from __future__ import annotations
from typing import Optional, List, Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_group.model import RateGroupModel
from rate_group.const.status import RateMethod
from rate_group.schemas.request import PaginateRateGroupRequest
from rate_group.schemas.response import RateGroupResponseSchema


class RateGroupRepository(TeamScopedRepoMixin):
    """
    RateGroup(정산/요율 그룹) 리포지토리
    - team 스코프 강제(_require_team)
    - method 별 is_default 유일성은 Service 가 clear_default_for_method 로 보장
    """

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ── Create ──────────────────────────────────────────────────
    async def create(self, payload: dict, actor_user_id: int | None = None) -> RateGroupModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = RateGroupModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    # ── Read ────────────────────────────────────────────────────
    async def get(self, group_id: int) -> Optional[RateGroupModel]:
        q = select(RateGroupModel).where(
            RateGroupModel.team_id == self._require_team(),
            RateGroupModel.id == group_id,
            RateGroupModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_default_for_method(self, method: RateMethod) -> Optional[RateGroupModel]:
        """방식의 활성 디폴트 그룹 — 해석 사다리 ④(상속 폴백)·미배정 기사 폴백 진입점."""
        q = (
            select(RateGroupModel)
            .where(
                RateGroupModel.team_id == self._require_team(),
                RateGroupModel.method == method,
                RateGroupModel.is_default.is_(True),
                RateGroupModel.is_active.is_(True),
            )
            .limit(1)
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, group_ids: List[int]) -> List[RateGroupModel]:
        if not group_ids:
            return []
        q = select(RateGroupModel).where(
            RateGroupModel.team_id == self._require_team(),
            RateGroupModel.id.in_(group_ids),
            RateGroupModel.is_active.is_(True),
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_paginated(
        self, request: PaginateRateGroupRequest
    ) -> CursorPaginationResult[RateGroupResponseSchema]:
        team_id = self._require_team()
        base_conditions = [RateGroupModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(RateGroupModel.is_active.is_(True))
        base_query = select(RateGroupModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request,
            model=RateGroupModel,
            session=self.db,
            base_query=base_query,
        )
        result.data = [RateGroupResponseSchema.model_validate(r) for r in result.data]
        return result

    # ── Update ──────────────────────────────────────────────────
    async def update(
        self, group_id: int, payload: dict, actor_user_id: int | None = None
    ) -> Optional[RateGroupModel]:
        if not payload:
            return await self.get(group_id)
        q = select(RateGroupModel).where(
            RateGroupModel.team_id == self._require_team(),
            RateGroupModel.id == group_id,
            RateGroupModel.is_active.is_(True),
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
        if not row:
            return None
        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id"}
        for k, v in payload.items():
            if k in protected:
                continue
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    # ── method 별 기본 그룹 유일성 ─────────────────────────────────
    async def clear_default_for_method(self, method: RateMethod, exclude_id: int | None = None) -> None:
        """같은 method 의 다른 그룹들의 is_default 를 False 로 — 기본 그룹 유일성 보장."""
        stmt = (
            update(RateGroupModel)
            .where(
                RateGroupModel.team_id == self._require_team(),
                RateGroupModel.method == method,
                RateGroupModel.is_default.is_(True),
            )
            .values(is_default=False, updated_at=func.utc_timestamp())
        )
        if exclude_id is not None:
            stmt = stmt.where(RateGroupModel.id != exclude_id)
        await self.db.execute(stmt)
        await self.db.flush()

    # ── Delete ──────────────────────────────────────────────────
    async def soft_deactivate_by_id(self, group_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(RateGroupModel)
            .where(
                RateGroupModel.team_id == self._require_team(),
                RateGroupModel.id == group_id,
                RateGroupModel.is_active.is_(True),
            )
            .values(**values)
        )
        await self.db.flush()

    async def hard_delete_by_id(self, group_id: int) -> None:
        await self.db.execute(
            delete(RateGroupModel).where(
                RateGroupModel.team_id == self._require_team(),
                RateGroupModel.id == group_id,
            )
        )
        await self.db.flush()

    async def get_existing_active_ids(self, ids: Iterable[int]) -> set[int]:
        id_list = list(ids)
        if not id_list:
            return set()
        stmt = select(RateGroupModel.id).where(
            RateGroupModel.team_id == self._require_team(),
            RateGroupModel.is_active.is_(True),
            RateGroupModel.id.in_(id_list),
        )
        result = await self.db.execute(stmt)
        return set(result.scalars().all())

    # ── Delta Sync ──────────────────────────────────────────────
    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(RateGroupModel).where(RateGroupModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=RateGroupModel,
            session=self.db,
            since=since,
            team_id=team_id,
            base_query=base_query,
            use_soft_delete=True,
        )
