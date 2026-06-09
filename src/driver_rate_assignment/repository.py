# src/driver_rate_assignment/repository.py
from __future__ import annotations
from typing import Optional, List, Iterable
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from driver_rate_assignment.model import DriverRateAssignmentModel
from driver_rate_assignment.schemas.request import PaginateDriverRateAssignmentRequest
from driver_rate_assignment.schemas.response import DriverRateAssignmentResponseSchema


class DriverRateAssignmentRepository(TeamScopedRepoMixin):
    """
    DriverRateAssignment(드라이버↔요율그룹 배정) 리포지토리
    - team 스코프 강제(_require_team)
    - 유효일자(effective_from ~ effective_to) 기반 조회
    """

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ── Create ──────────────────────────────────────────────────
    async def create(self, payload: dict, actor_user_id: int | None = None) -> DriverRateAssignmentModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = DriverRateAssignmentModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    # ── Read ────────────────────────────────────────────────────
    async def get(self, assignment_id: int) -> Optional[DriverRateAssignmentModel]:
        q = select(DriverRateAssignmentModel).where(
            DriverRateAssignmentModel.team_id == self._require_team(),
            DriverRateAssignmentModel.id == assignment_id,
            DriverRateAssignmentModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, assignment_ids: List[int]) -> List[DriverRateAssignmentModel]:
        if not assignment_ids:
            return []
        q = select(DriverRateAssignmentModel).where(
            DriverRateAssignmentModel.team_id == self._require_team(),
            DriverRateAssignmentModel.id.in_(assignment_ids),
            DriverRateAssignmentModel.is_active.is_(True),
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_active_for_driver(
        self, driver_id: int, work_date: date
    ) -> Optional[DriverRateAssignmentModel]:
        """work_date 기준 유효한 배정 1건(가장 최근 effective_from)."""
        q = (
            select(DriverRateAssignmentModel)
            .where(
                DriverRateAssignmentModel.team_id == self._require_team(),
                DriverRateAssignmentModel.driver_id == driver_id,
                DriverRateAssignmentModel.is_active.is_(True),
                DriverRateAssignmentModel.effective_from <= work_date,
                or_(
                    DriverRateAssignmentModel.effective_to.is_(None),
                    DriverRateAssignmentModel.effective_to >= work_date,
                ),
            )
            .order_by(DriverRateAssignmentModel.effective_from.desc())
            .limit(1)
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_paginated(
        self, request: PaginateDriverRateAssignmentRequest
    ) -> CursorPaginationResult[DriverRateAssignmentResponseSchema]:
        team_id = self._require_team()
        base_conditions = [DriverRateAssignmentModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(DriverRateAssignmentModel.is_active.is_(True))
        base_query = select(DriverRateAssignmentModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request,
            model=DriverRateAssignmentModel,
            session=self.db,
            base_query=base_query,
        )
        result.data = [DriverRateAssignmentResponseSchema.model_validate(r) for r in result.data]
        return result

    # ── Update ──────────────────────────────────────────────────
    async def update(
        self, assignment_id: int, payload: dict, actor_user_id: int | None = None
    ) -> Optional[DriverRateAssignmentModel]:
        if not payload:
            return await self.get(assignment_id)
        q = select(DriverRateAssignmentModel).where(
            DriverRateAssignmentModel.team_id == self._require_team(),
            DriverRateAssignmentModel.id == assignment_id,
            DriverRateAssignmentModel.is_active.is_(True),
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
        if not row:
            return None
        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id", "driver_id"}
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
    async def soft_deactivate_by_id(self, assignment_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(DriverRateAssignmentModel)
            .where(
                DriverRateAssignmentModel.team_id == self._require_team(),
                DriverRateAssignmentModel.id == assignment_id,
                DriverRateAssignmentModel.is_active.is_(True),
            )
            .values(**values)
        )
        await self.db.flush()

    async def hard_delete_by_id(self, assignment_id: int) -> None:
        await self.db.execute(
            delete(DriverRateAssignmentModel).where(
                DriverRateAssignmentModel.team_id == self._require_team(),
                DriverRateAssignmentModel.id == assignment_id,
            )
        )
        await self.db.flush()

    async def get_existing_active_ids(self, ids: Iterable[int]) -> set[int]:
        id_list = list(ids)
        if not id_list:
            return set()
        stmt = select(DriverRateAssignmentModel.id).where(
            DriverRateAssignmentModel.team_id == self._require_team(),
            DriverRateAssignmentModel.is_active.is_(True),
            DriverRateAssignmentModel.id.in_(id_list),
        )
        result = await self.db.execute(stmt)
        return set(result.scalars().all())

    # ── Delta Sync ──────────────────────────────────────────────
    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(DriverRateAssignmentModel).where(DriverRateAssignmentModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=DriverRateAssignmentModel,
            session=self.db,
            since=since,
            team_id=team_id,
            base_query=base_query,
            use_soft_delete=True,
        )
