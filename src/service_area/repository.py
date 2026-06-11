# src/service_area/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from service_area.model import ServiceAreaModel
from service_area.schemas.request import PaginateServiceAreaRequest


class ServiceAreaRepository(TeamScopedRepoMixin):
    """영업권역 선언 리포지토리 — team 스코프 강제(_require_team)."""

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def create(self, payload: dict, actor_user_id: int | None = None) -> ServiceAreaModel:
        payload["team_id"] = self._require_team()
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = ServiceAreaModel(**payload)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def get(self, area_id: int) -> Optional[ServiceAreaModel]:
        q = select(ServiceAreaModel).where(
            ServiceAreaModel.team_id == self._require_team(),
            ServiceAreaModel.id == area_id,
            ServiceAreaModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_duplicate(self, kind, state: str, value: str) -> Optional[ServiceAreaModel]:
        """is_active 무관 조회 — uq(team,kind,state,value)가 비활성 행도 점유하므로 업서트/되살림용."""
        q = select(ServiceAreaModel).where(
            ServiceAreaModel.team_id == self._require_team(),
            ServiceAreaModel.kind == kind,
            ServiceAreaModel.state == state,
            ServiceAreaModel.value == value,
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_active(self) -> List[ServiceAreaModel]:
        """팀의 활성 선언 전부 — zip/도시 검색 스코프 필터 변환용 (행 수 소량)."""
        q = select(ServiceAreaModel).where(
            ServiceAreaModel.team_id == self._require_team(),
            ServiceAreaModel.is_active.is_(True),
        ).order_by(ServiceAreaModel.id.asc())
        return list((await self.db.execute(q)).scalars().all())

    async def get_paginated(self, request: PaginateServiceAreaRequest):
        team_id = self._require_team()
        base = [ServiceAreaModel.team_id == team_id]
        if not request.include_inactive:
            base.append(ServiceAreaModel.is_active.is_(True))
        return await self._common_service.paginate(
            request=request, model=ServiceAreaModel, session=self.db,
            base_query=select(ServiceAreaModel).where(*base),
        )

    async def soft_deactivate_by_id(self, area_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(ServiceAreaModel).where(
                ServiceAreaModel.team_id == self._require_team(),
                ServiceAreaModel.id == area_id,
                ServiceAreaModel.is_active.is_(True),
            ).values(**values)
        )
        await self.db.flush()

    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(ServiceAreaModel).where(ServiceAreaModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=ServiceAreaModel, session=self.db, since=since,
            team_id=team_id, base_query=base_query, use_soft_delete=True,
        )
