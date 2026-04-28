# src/leg_stop/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from leg_stop.model import LegStopModel
from leg_stop.schemas.request import PaginateLegStopRequest
from leg_stop.schemas.response import LegStopResponseSchema


class LegStopRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> LegStopModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = LegStopModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, id_: int) -> Optional[LegStopModel]:
        q = select(LegStopModel).where(
            LegStopModel.team_id == self._require_team(),
            LegStopModel.id == id_,
            LegStopModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, ids: List[int]) -> List[LegStopModel]:
        if not ids:
            return []
        q = select(LegStopModel).where(
            LegStopModel.team_id == self._require_team(),
            LegStopModel.id.in_(ids),
            LegStopModel.is_active.is_(True),
        )
        return list((await self.db.execute(q)).scalars().all())

    async def list_by_leg(self, leg_id: int) -> List[LegStopModel]:
        q = (
            select(LegStopModel)
            .where(
                LegStopModel.team_id == self._require_team(),
                LegStopModel.leg_id == leg_id,
                LegStopModel.is_active.is_(True),
            )
            .order_by(LegStopModel.sequence_no.asc(), LegStopModel.id.asc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_paginated(
        self, request: PaginateLegStopRequest,
    ) -> CursorPaginationResult[LegStopResponseSchema]:
        team_id = self._require_team()
        base_conditions = [LegStopModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(LegStopModel.is_active.is_(True))
        base_query = select(LegStopModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request, model=LegStopModel,
            session=self.db, base_query=base_query,
        )
        result.data = [LegStopResponseSchema.model_validate(r) for r in result.data]
        return result

    async def next_sequence_no(self, leg_id: int) -> int:
        team_id = self._require_team()
        q = select(func.max(LegStopModel.sequence_no)).where(
            LegStopModel.team_id == team_id,
            LegStopModel.leg_id == leg_id,
        )
        result = await self.db.execute(q)
        return (result.scalar() or 0) + 1

    async def update(
        self, id_: int, payload: dict, actor_user_id: int | None = None,
    ) -> Optional[LegStopModel]:
        if not payload:
            return await self.get(id_)
        q = select(LegStopModel).where(
            LegStopModel.team_id == self._require_team(),
            LegStopModel.id == id_,
            LegStopModel.is_active.is_(True),
        )
        row = (await self.db.execute(q)).scalar_one_or_none()
        if not row:
            return None
        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id", "leg_id"}
        for k, v in payload.items():
            if k in protected:
                continue
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def soft_deactivate_by_id(
        self, id_: int, actor_user_id: int | None = None,
    ) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(LegStopModel).where(
                LegStopModel.team_id == self._require_team(),
                LegStopModel.id == id_,
                LegStopModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def hard_delete_by_id(self, id_: int) -> None:
        await self.db.execute(
            delete(LegStopModel).where(
                LegStopModel.team_id == self._require_team(),
                LegStopModel.id == id_,
            )
        )
        await self.db.flush()
