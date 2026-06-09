# src/accessorial/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from accessorial.model import AccessorialModel
from accessorial.schemas.request import PaginateAccessorialRequest
from accessorial.schemas.response import AccessorialResponseSchema


class AccessorialRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> AccessorialModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = AccessorialModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, acc_id: int) -> Optional[AccessorialModel]:
        q = select(AccessorialModel).where(
            AccessorialModel.team_id == self._require_team(),
            AccessorialModel.id == acc_id,
            AccessorialModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def find_for_code(self, code: str, driver_id: int | None = None) -> Optional[AccessorialModel]:
        """code 의 정의를 조회 — driver override 우선, 없으면 전역."""
        if driver_id is not None:
            q = select(AccessorialModel).where(
                AccessorialModel.team_id == self._require_team(),
                AccessorialModel.code == code,
                AccessorialModel.driver_id == driver_id,
                AccessorialModel.is_active.is_(True),
            )
            row = (await self.db.execute(q)).scalar_one_or_none()
            if row is not None:
                return row
        q = select(AccessorialModel).where(
            AccessorialModel.team_id == self._require_team(),
            AccessorialModel.code == code,
            AccessorialModel.driver_id.is_(None),
            AccessorialModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_paginated(self, request: PaginateAccessorialRequest):
        team_id = self._require_team()
        base = [AccessorialModel.team_id == team_id]
        if not request.include_inactive:
            base.append(AccessorialModel.is_active.is_(True))
        return await self._common_service.paginate(
            request=request, model=AccessorialModel, session=self.db,
            base_query=select(AccessorialModel).where(*base),
        )

    async def update(self, acc_id: int, payload: dict, actor_user_id: int | None = None) -> Optional[AccessorialModel]:
        if not payload:
            return await self.get(acc_id)
        row = await self.get(acc_id)
        if not row:
            return None
        for k, v in payload.items():
            if k in {"id", "team_id", "is_active", "created_at", "created_by_user_id", "code", "driver_id"}:
                continue
            setattr(row, k, v)
        if actor_user_id is not None:
            row.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def soft_deactivate_by_id(self, acc_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(AccessorialModel).where(
                AccessorialModel.team_id == self._require_team(),
                AccessorialModel.id == acc_id,
                AccessorialModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(AccessorialModel).where(AccessorialModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=AccessorialModel, session=self.db, since=since,
            team_id=team_id, base_query=base_query, use_soft_delete=True,
        )
