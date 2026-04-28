# src/chassis_event/repository.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from chassis_event.model import ChassisEventModel
from chassis_event.schemas.request import PaginateChassisEventRequest
from chassis_event.schemas.response import ChassisEventResponseSchema


class ChassisEventRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> ChassisEventModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = ChassisEventModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def list_by_chassis(self, chassis_id: int) -> List[ChassisEventModel]:
        q = (
            select(ChassisEventModel)
            .where(
                ChassisEventModel.team_id == self._require_team(),
                ChassisEventModel.chassis_id == chassis_id,
                ChassisEventModel.is_active.is_(True),
            )
            .order_by(ChassisEventModel.occurred_at.desc(), ChassisEventModel.id.desc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_paginated(
        self, request: PaginateChassisEventRequest,
    ) -> CursorPaginationResult[ChassisEventResponseSchema]:
        team_id = self._require_team()
        base_conditions = [ChassisEventModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(ChassisEventModel.is_active.is_(True))
        base_query = select(ChassisEventModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request, model=ChassisEventModel,
            session=self.db, base_query=base_query,
        )
        result.data = [ChassisEventResponseSchema.model_validate(r) for r in result.data]
        return result
