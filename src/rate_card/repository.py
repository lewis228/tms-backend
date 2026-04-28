# src/rate_card/repository.py
from __future__ import annotations
from typing import Optional, List, Iterable

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_card.model import RateCardModel
from rate_card.schemas.request import PaginateRateCardRequest
from rate_card.schemas.response import RateCardResponseSchema


class RateCardRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> RateCardModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = RateCardModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, id_: int) -> Optional[RateCardModel]:
        q = select(RateCardModel).where(
            RateCardModel.team_id == self._require_team(),
            RateCardModel.id == id_,
            RateCardModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_many(self, ids: List[int]) -> List[RateCardModel]:
        if not ids:
            return []
        q = select(RateCardModel).where(
            RateCardModel.team_id == self._require_team(),
            RateCardModel.id.in_(ids),
            RateCardModel.is_active.is_(True),
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_paginated(
        self, request: PaginateRateCardRequest,
    ) -> CursorPaginationResult[RateCardResponseSchema]:
        team_id = self._require_team()
        base_conditions = [RateCardModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(RateCardModel.is_active.is_(True))
        base_query = select(RateCardModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request, model=RateCardModel,
            session=self.db, base_query=base_query,
        )
        result.data = [RateCardResponseSchema.model_validate(r) for r in result.data]
        return result

    async def update(
        self, id_: int, payload: dict, actor_user_id: int | None = None,
    ) -> Optional[RateCardModel]:
        if not payload:
            return await self.get(id_)
        q = select(RateCardModel).where(
            RateCardModel.team_id == self._require_team(),
            RateCardModel.id == id_,
            RateCardModel.is_active.is_(True),
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

    async def soft_deactivate_by_id(
        self, id_: int, actor_user_id: int | None = None,
    ) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(RateCardModel).where(
                RateCardModel.team_id == self._require_team(),
                RateCardModel.id == id_,
                RateCardModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def hard_delete_by_id(self, id_: int) -> None:
        await self.db.execute(
            delete(RateCardModel).where(
                RateCardModel.team_id == self._require_team(),
                RateCardModel.id == id_,
            )
        )
        await self.db.flush()

    async def get_existing_active_ids(self, ids: Iterable[int]) -> set[int]:
        id_list = list(ids)
        if not id_list:
            return set()
        stmt = select(RateCardModel.id).where(
            RateCardModel.team_id == self._require_team(),
            RateCardModel.is_active.is_(True),
            RateCardModel.id.in_(id_list),
        )
        return set((await self.db.execute(stmt)).scalars().all())
