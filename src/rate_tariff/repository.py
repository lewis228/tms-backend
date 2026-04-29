# src/rate_tariff/repository.py
from __future__ import annotations
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from rate_tariff.model import RateTariffModel
from rate_tariff.schemas.request import PaginateRateTariffRequest


class RateTariffRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> RateTariffModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = RateTariffModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, id_: int) -> Optional[RateTariffModel]:
        q = select(RateTariffModel).where(
            RateTariffModel.team_id == self._require_team(),
            RateTariffModel.id == id_,
            RateTariffModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_paginated(self, request: PaginateRateTariffRequest):
        team_id = self._require_team()
        base = [RateTariffModel.team_id == team_id]
        if not request.include_inactive:
            base.append(RateTariffModel.is_active.is_(True))
        base_query = select(RateTariffModel).where(*base)
        return await self._common_service.paginate(
            request=request, model=RateTariffModel,
            session=self.db, base_query=base_query,
        )

    async def update(self, id_: int, payload: dict, actor_user_id: int | None = None) -> Optional[RateTariffModel]:
        if not payload:
            return await self.get(id_)
        row = (await self.db.execute(select(RateTariffModel).where(
            RateTariffModel.team_id == self._require_team(),
            RateTariffModel.id == id_,
            RateTariffModel.is_active.is_(True),
        ))).scalar_one_or_none()
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

    async def soft_deactivate_by_id(self, id_: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(update(RateTariffModel).where(
            RateTariffModel.team_id == self._require_team(),
            RateTariffModel.id == id_,
            RateTariffModel.is_active.is_(True),
        ).values(**values))
        await self.db.flush()
