# src/dual_transaction/repository.py
from __future__ import annotations
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from dual_transaction.model import DualTransactionModel
from dual_transaction.schemas.request import PaginateDualTransactionRequest


class DualTransactionRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> DualTransactionModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = DualTransactionModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, dtx_id: int) -> Optional[DualTransactionModel]:
        q = select(DualTransactionModel).where(
            DualTransactionModel.team_id == self._require_team(),
            DualTransactionModel.id == dtx_id,
            DualTransactionModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_paginated(self, request: PaginateDualTransactionRequest):
        team_id = self._require_team()
        base = [DualTransactionModel.team_id == team_id]
        if not request.include_inactive:
            base.append(DualTransactionModel.is_active.is_(True))
        return await self._common_service.paginate(
            request=request, model=DualTransactionModel, session=self.db,
            base_query=select(DualTransactionModel).where(*base),
        )

    async def soft_deactivate_by_id(self, dtx_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(update(DualTransactionModel).where(
            DualTransactionModel.team_id == self._require_team(),
            DualTransactionModel.id == dtx_id,
            DualTransactionModel.is_active.is_(True),
        ).values(**values))
        await self.db.flush()

    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(DualTransactionModel).where(DualTransactionModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=DualTransactionModel, session=self.db, since=since,
            team_id=team_id, base_query=base_query, use_soft_delete=True,
        )
