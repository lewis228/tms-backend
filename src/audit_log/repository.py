# src/audit_log/repository.py
from __future__ import annotations
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from audit_log.model import AuditLogModel
from audit_log.schemas.request import PaginateAuditLogRequest


class AuditLogRepository(TeamScopedRepoMixin):
    """append-only — create + 조회만."""

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def record(self, payload: dict, actor_user_id: int | None = None) -> AuditLogModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = AuditLogModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def list_for_entity(self, entity_type: str, entity_id: int, limit: int = 200) -> List[AuditLogModel]:
        q = (
            select(AuditLogModel)
            .where(
                AuditLogModel.team_id == self._require_team(),
                AuditLogModel.entity_type == entity_type,
                AuditLogModel.entity_id == entity_id,
            )
            .order_by(AuditLogModel.id.desc())
            .limit(limit)
        )
        return list((await self.db.execute(q)).scalars().all())

    async def get_paginated(self, request: PaginateAuditLogRequest):
        team_id = self._require_team()
        return await self._common_service.paginate(
            request=request, model=AuditLogModel, session=self.db,
            base_query=select(AuditLogModel).where(AuditLogModel.team_id == team_id),
        )
