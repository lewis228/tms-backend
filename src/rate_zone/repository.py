# src/rate_zone/repository.py
from __future__ import annotations
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_, and_
from sqlalchemy.orm import selectinload

from common.repository.team_scoped import TeamScopedRepoMixin
from common.pagination.service import CommonService
from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_zone.model import RateZoneModel, RateZoneMemberModel
from rate_zone.const.status import ZoneKind
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
                city=m.get("city"),
                state=m.get("state"),
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

    def _scoped_zone_query(self, rate_group_id: int | None, kind):
        """원자→zone 조회 공통: 그룹 스코프 존 우선, 없으면 글로벌(NULL) 존.

        rate_group_id 가 None 이면 글로벌 존만 본다.
        kind 로 존 종류 필터 — ZIP 방식은 ZIP존만, CITY 방식은 도시존만 매칭.
        """
        scope_cond = (
            RateZoneModel.rate_group_id.is_(None)
            if rate_group_id is None
            else or_(
                RateZoneModel.rate_group_id == rate_group_id,
                RateZoneModel.rate_group_id.is_(None),
            )
        )
        q = (
            select(RateZoneMemberModel.zone_id)
            .join(RateZoneModel, RateZoneModel.id == RateZoneMemberModel.zone_id)
            .where(
                RateZoneMemberModel.team_id == self._require_team(),
                RateZoneModel.is_active.is_(True),
                RateZoneModel.kind == kind,
                scope_cond,
            )
            # 그룹 스코프 존(NULL 아님) 먼저, 그 안에선 결정적으로 가장 작은 zone_id.
            .order_by(
                RateZoneModel.rate_group_id.is_(None).asc(),
                RateZoneMemberModel.zone_id.asc(),
            )
            .limit(1)
        )
        return q

    async def resolve_zone_id_for_zip(
        self, zip_code: str, rate_group_id: int | None = None
    ) -> Optional[int]:
        """zip → 활성 ZIP존 id (해석 진입점). 그룹 스코프 존 > 글로벌 존."""
        q = self._scoped_zone_query(rate_group_id, ZoneKind.ZIP).where(
            RateZoneMemberModel.zip_code == zip_code,
        )
        return (await self.db.execute(q)).scalar_one_or_none()

    async def resolve_zone_id_for_city(
        self, city: str, state: str | None, rate_group_id: int | None = None
    ) -> Optional[int]:
        """(city,state) → 활성 도시존 id (CITY 방식 전용). 그룹 스코프 존 > 글로벌 존."""
        conds = [func.lower(RateZoneMemberModel.city) == city.lower()]
        if state:
            conds.append(RateZoneMemberModel.state == state.upper())
        q = self._scoped_zone_query(rate_group_id, ZoneKind.CITY).where(*conds)
        return (await self.db.execute(q)).scalar_one_or_none()

    async def list_conflicting_atoms(
        self, zone_id: int | None, scope_group_id: int | None,
        zips: List[str], cities: List[tuple[str, str | None]],
    ) -> List[tuple[str, str]]:
        """같은 스코프(글로벌 / 특정 그룹)의 *다른* 활성 존에 이미 속한 원자들.

        제약 "같은 스코프 안에서 원자당 존 1개" 의 앱 레벨 검사
        (MySQL 유니크는 NULL 스코프를 표현 못 함). 반환 = [(원자 라벨, 존 이름)].
        """
        if not zips and not cities:
            return []
        scope_cond = (
            RateZoneModel.rate_group_id.is_(None)
            if scope_group_id is None
            else RateZoneModel.rate_group_id == scope_group_id
        )
        atom_conds = []
        if zips:
            atom_conds.append(RateZoneMemberModel.zip_code.in_(zips))
        for c, s in cities:
            cc = [func.lower(RateZoneMemberModel.city) == c.lower()]
            if s:
                cc.append(RateZoneMemberModel.state == s.upper())
            atom_conds.append(and_(*cc))
        conds = [
            RateZoneMemberModel.team_id == self._require_team(),
            RateZoneModel.is_active.is_(True),
            scope_cond,
            or_(*atom_conds),
        ]
        if zone_id is not None:
            conds.append(RateZoneModel.id != zone_id)
        q = (
            select(RateZoneMemberModel, RateZoneModel.name)
            .join(RateZoneModel, RateZoneModel.id == RateZoneMemberModel.zone_id)
            .where(*conds)
        )
        rows = (await self.db.execute(q)).all()
        out: List[tuple[str, str]] = []
        for member, zone_name in rows:
            label = member.zip_code if member.zip_code else f"{member.city}, {member.state or ''}".rstrip(", ")
            out.append((label, zone_name))
        return out

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
                city=m.get("city"),
                state=m.get("state"),
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
