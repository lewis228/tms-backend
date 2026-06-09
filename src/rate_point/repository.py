# src/rate_point/repository.py
from __future__ import annotations
from typing import Optional, List, Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_point.model import RatePointModel
from rate_point.schemas.request import PaginateRatePointRequest
from rate_point.schemas.response import RatePointResponseSchema


class RatePointRepository(TeamScopedRepoMixin):
    """
    RatePoint(요율표 행: Terminal/Yard) 리포지토리
    - team 스코프 강제(_require_team)
    - 기본 is_active=True
    """

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ── Create ──────────────────────────────────────────────────
    async def create(self, payload: dict, actor_user_id: int | None = None) -> RatePointModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = RatePointModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def create_many(self, payloads: List[dict], actor_user_id: int | None = None) -> List[RatePointModel]:
        team_id = self._require_team()
        rows = []
        for payload in payloads:
            payload["team_id"] = team_id
            if actor_user_id is not None:
                payload["created_by_user_id"] = actor_user_id
            row = RatePointModel(**payload)
            self.db.add(row)
            rows.append(row)
        await self.db.flush()
        for row in rows:
            await self.db.refresh(row)
        return rows

    # ── Read ────────────────────────────────────────────────────
    async def get(self, point_id: int) -> Optional[RatePointModel]:
        q = select(RatePointModel).where(
            RatePointModel.team_id == self._require_team(),
            RatePointModel.id == point_id,
            RatePointModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, point_ids: List[int]) -> List[RatePointModel]:
        if not point_ids:
            return []
        q = select(RatePointModel).where(
            RatePointModel.team_id == self._require_team(),
            RatePointModel.id.in_(point_ids),
            RatePointModel.is_active.is_(True),
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_paginated(
        self, request: PaginateRatePointRequest
    ) -> CursorPaginationResult[RatePointResponseSchema]:
        team_id = self._require_team()

        base_conditions = [RatePointModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(RatePointModel.is_active.is_(True))

        base_query = select(RatePointModel).where(*base_conditions)

        result = await self._common_service.paginate(
            request=request,
            model=RatePointModel,
            session=self.db,
            base_query=base_query,
        )
        result.data = [RatePointResponseSchema.model_validate(r) for r in result.data]
        return result

    # ── Update ──────────────────────────────────────────────────
    async def update(
        self, point_id: int, payload: dict, actor_user_id: int | None = None
    ) -> Optional[RatePointModel]:
        if not payload:
            return await self.get(point_id)

        q = select(RatePointModel).where(
            RatePointModel.team_id == self._require_team(),
            RatePointModel.id == point_id,
            RatePointModel.is_active.is_(True),
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

    # ── Delete ──────────────────────────────────────────────────
    async def soft_deactivate_by_id(self, point_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(RatePointModel)
            .where(
                RatePointModel.team_id == self._require_team(),
                RatePointModel.id == point_id,
                RatePointModel.is_active.is_(True),
            )
            .values(**values)
        )
        await self.db.flush()

    async def hard_delete_by_id(self, point_id: int) -> None:
        await self.db.execute(
            delete(RatePointModel).where(
                RatePointModel.team_id == self._require_team(),
                RatePointModel.id == point_id,
            )
        )
        await self.db.flush()

    # ── 존재 검증 ────────────────────────────────────────────────
    async def get_existing_active_ids(self, ids: Iterable[int]) -> set[int]:
        id_list = list(ids)
        if not id_list:
            return set()
        stmt = select(RatePointModel.id).where(
            RatePointModel.team_id == self._require_team(),
            RatePointModel.is_active.is_(True),
            RatePointModel.id.in_(id_list),
        )
        result = await self.db.execute(stmt)
        return set(result.scalars().all())

    # ── Delta Sync ──────────────────────────────────────────────
    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(RatePointModel).where(RatePointModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=RatePointModel,
            session=self.db,
            since=since,
            team_id=team_id,
            base_query=base_query,
            use_soft_delete=True,
        )
