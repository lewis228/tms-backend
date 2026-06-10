# src/rate_zone/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_zone.model import RateZoneModel, RateZoneMemberModel
from rate_zone.schemas.request import PaginateRateZoneRequest
from rate_zone.schemas.response import RateZoneSummarySchema, RateZoneResponseSchema  # noqa: F401


class RateZoneRepository(TeamScopedRepoMixin):
    """
    RateZone(요율표 열: Zone) + RateZoneMember(zip) 리포지토리.
    - team 스코프 강제(_require_team)
    - 헤더(zone) + 라인(member) 복합 FK
    - 조회는 zip→zone 인덱스(member) 기반
    """

    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    # ── Create ──────────────────────────────────────────────────
    async def create(
        self, payload: dict, members: List[dict], actor_user_id: int | None = None
    ) -> RateZoneModel:
        team_id = self._require_team()
        payload["team_id"] = team_id
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        zone = RateZoneModel(**payload)
        self.db.add(zone)
        await self.db.flush()  # zone.id 확보

        for m in members:
            self.db.add(RateZoneMemberModel(
                team_id=team_id,
                zone_id=zone.id,
                zip_code=m.get("zip_code"),
                created_by_user_id=actor_user_id,
            ))
        await self.db.flush()
        return await self.get_with_members(zone.id)

    # ── Read ────────────────────────────────────────────────────
    async def get_with_members(self, zone_id: int) -> Optional[RateZoneModel]:
        q = (
            select(RateZoneModel)
            .where(
                RateZoneModel.team_id == self._require_team(),
                RateZoneModel.id == zone_id,
                RateZoneModel.is_active.is_(True),
            )
            .options(selectinload(RateZoneModel.members))
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_header(self, zone_id: int) -> Optional[RateZoneModel]:
        q = select(RateZoneModel).where(
            RateZoneModel.team_id == self._require_team(),
            RateZoneModel.id == zone_id,
            RateZoneModel.is_active.is_(True),
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def get_paginated(
        self, request: PaginateRateZoneRequest
    ) -> CursorPaginationResult[RateZoneResponseSchema]:
        team_id = self._require_team()
        base_conditions = [RateZoneModel.team_id == team_id]
        if not request.include_inactive:
            base_conditions.append(RateZoneModel.is_active.is_(True))
        base_query = select(RateZoneModel).where(*base_conditions)
        result = await self._common_service.paginate(
            request=request,
            model=RateZoneModel,
            session=self.db,
            base_query=base_query,
        )
        # 목록은 헤더만 (members 미포함)
        result.data = [RateZoneSummarySchema.model_validate(r) for r in result.data]
        return result

    async def list_members(self, zone_id: int) -> List[RateZoneMemberModel]:
        q = (
            select(RateZoneMemberModel)
            .where(
                RateZoneMemberModel.team_id == self._require_team(),
                RateZoneMemberModel.zone_id == zone_id,
            )
            .order_by(RateZoneMemberModel.id.asc())
        )
        return list((await self.db.execute(q)).scalars().all())

    async def resolve_zone_id_by_zip(self, zip_code: str) -> Optional[int]:
        """zip → 활성 zone_id (정산/요율 조회 진입점). 매칭 없으면 None."""
        q = (
            select(RateZoneMemberModel.zone_id)
            .join(RateZoneModel, RateZoneModel.id == RateZoneMemberModel.zone_id)
            .where(
                RateZoneMemberModel.team_id == self._require_team(),
                RateZoneMemberModel.zip_code == zip_code,
                RateZoneModel.is_active.is_(True),
            )
            .limit(1)
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    # ── Update ──────────────────────────────────────────────────
    async def update_header(
        self, zone_id: int, payload: dict, actor_user_id: int | None = None
    ) -> Optional[RateZoneModel]:
        zone = await self.get_header(zone_id)
        if not zone:
            return None
        protected = {"id", "team_id", "is_active", "created_at", "created_by_user_id"}
        for k, v in payload.items():
            if k in protected:
                continue
            setattr(zone, k, v)
        if actor_user_id is not None:
            zone.updated_by_user_id = actor_user_id
        await self.db.flush()
        return await self.get_with_members(zone_id)

    async def replace_members(
        self, zone_id: int, members: List[dict], actor_user_id: int | None = None
    ) -> List[RateZoneMemberModel]:
        """Zone 의 멤버 전체 교체 (delete-all + insert)."""
        team_id = self._require_team()
        await self.db.execute(
            delete(RateZoneMemberModel).where(
                RateZoneMemberModel.team_id == team_id,
                RateZoneMemberModel.zone_id == zone_id,
            )
        )
        for m in members:
            self.db.add(RateZoneMemberModel(
                team_id=team_id,
                zone_id=zone_id,
                zip_code=m.get("zip_code"),
                created_by_user_id=actor_user_id,
            ))
        await self.db.flush()
        return await self.list_members(zone_id)

    # ── Delete ──────────────────────────────────────────────────
    async def soft_deactivate_by_id(self, zone_id: int, actor_user_id: int | None = None) -> None:
        values = {"is_active": False, "updated_at": func.utc_timestamp()}
        if actor_user_id is not None:
            values["updated_by_user_id"] = actor_user_id
        await self.db.execute(
            update(RateZoneModel)
            .where(
                RateZoneModel.team_id == self._require_team(),
                RateZoneModel.id == zone_id,
                RateZoneModel.is_active.is_(True),
            )
            .values(**values)
        )
        await self.db.flush()

    # ── Delta Sync ──────────────────────────────────────────────
    async def sync_delta(self, since):
        team_id = self._require_team()
        base_query = select(RateZoneModel).where(RateZoneModel.team_id == team_id)
        return await self._common_service.sync_delta(
            model=RateZoneModel,
            session=self.db,
            since=since,
            team_id=team_id,
            base_query=base_query,
            use_soft_delete=True,
        )
