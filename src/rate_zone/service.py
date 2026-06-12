# src/rate_zone/service.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from common.exceptions.base import NotFoundException, AppException
from common.pagination.schemas.pagination_response import CursorPaginationResult
from realtime.emit import emit_entity_event
from rate_zone.repository import RateZoneRepository
from rate_zone.const.status import ZoneKind
from zip_code.repository import ZipCodeRepository
from rate_zone.schemas.request import (
    RateZoneCreateRequest, RateZoneUpdateRequest, PaginateRateZoneRequest,
    RateZoneMembersReplaceRequest,
)
from rate_zone.schemas.response import (
    RateZoneResponseSchema, RateZoneSummarySchema, RateZoneDeleteResponseSchema,
    RateZoneMemberResponseSchema, RateZoneMembersResponseSchema,
)

_LABEL = "Rate Zone"


class RateZoneService:
    """
    RateZone(요율표 열: Zone) 비즈니스 로직.

    - Zone 헤더 + zip 멤버. 멤버는 zip→zone 조회의 진실(폴리곤 연산 아님).
    - 삭제는 항상 소프트(is_active=False) — 과거 Rate Sheet/Invoice 이력 보존.
    """
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = RateZoneRepository(db, team_id)

    # ── 내부 검증 ────────────────────────────────────────────────
    @staticmethod
    def _check_kind_match(kind, members_data: list[dict]) -> None:
        """존 종류와 멤버 원자 타입 일치 강제 — 혼합 금지 (사용자 확정).

        ZIP존 = zip 멤버만 / 도시존 = (city,state) 멤버만.
        """
        bad = None
        if kind == ZoneKind.ZIP:
            if any(m.get("city") for m in members_data):
                bad = "ZIP존에는 도시 멤버를 넣을 수 없습니다 (도시의 zip 을 넣으려면 '도시로 추가'를 사용)."
        else:  # CITY
            if any(m.get("zip_code") for m in members_data):
                bad = "도시존에는 zip 멤버를 넣을 수 없습니다 (도시존은 CITY 방식 전용 — 도시만)."
        if bad:
            raise AppException(code="ZONE_KIND_MISMATCH", message=bad, status_code=422)

    async def _validate_group(self, rate_group_id: int | None) -> None:
        """그룹 스코프 존이면 그룹 존재 확인 (ste 규약: 다른 도메인 Repository 직접 주입)."""
        if rate_group_id is None:
            return
        from rate_group.repository import RateGroupRepository
        group = await RateGroupRepository(self.db, self.team_id).get(rate_group_id)
        if group is None:
            raise NotFoundException("Rate Group")

    async def _check_atom_conflicts(
        self, zone_id: int | None, scope_group_id: int | None, members_data: list[dict]
    ) -> None:
        """같은 스코프 내 원자당 존 1개 — 다른 존에 이미 속한 원자가 있으면 409."""
        zips = [m["zip_code"] for m in members_data if m.get("zip_code")]
        cities = [(m["city"], m.get("state")) for m in members_data if m.get("city")]
        conflicts = await self.repo.list_conflicting_atoms(zone_id, scope_group_id, zips, cities)
        if conflicts:
            detail = ", ".join(f"{atom} → '{zone}'" for atom, zone in conflicts[:10])
            raise AppException(
                code="ZONE_MEMBER_CONFLICT",
                message=f"같은 스코프의 다른 존에 이미 속한 멤버가 있습니다: {detail}",
                status_code=409,
            )

    # ── Create ──────────────────────────────────────────────────
    async def create(
        self, payload: RateZoneCreateRequest, actor_user_id: int | None = None
    ) -> RateZoneResponseSchema:
        await self._validate_group(payload.rate_group_id)
        header = payload.model_dump(exclude={"members"})
        members = [m.model_dump() for m in payload.members]
        self._check_kind_match(payload.kind, members)
        await self._check_atom_conflicts(None, payload.rate_group_id, members)
        zone = await self.repo.create(header, members, actor_user_id=actor_user_id)
        await emit_entity_event("rate_zone.created", self.team_id,
                                {"rateZoneId": zone.id}, actor_user_id)
        return RateZoneResponseSchema.model_validate(zone)

    # ── Read ────────────────────────────────────────────────────
    async def get(self, zone_id: int) -> RateZoneResponseSchema:
        zone = await self.repo.get_with_members(zone_id)
        if not zone:
            raise NotFoundException(_LABEL)
        return RateZoneResponseSchema.model_validate(zone)

    async def list_paginated(
        self, request: PaginateRateZoneRequest
    ) -> CursorPaginationResult[RateZoneSummarySchema]:
        result = await self.repo.get_paginated(request)
        result.data = [RateZoneSummarySchema.model_validate(r) for r in result.data]
        return result

    async def list_members(self, zone_id: int) -> RateZoneMembersResponseSchema:
        zone = await self.repo.get_header(zone_id)
        if not zone:
            raise NotFoundException(_LABEL)
        rows = await self.repo.list_members(zone_id)
        members = [RateZoneMemberResponseSchema.model_validate(r) for r in rows]
        return RateZoneMembersResponseSchema(zone_id=zone_id, members=members, count=len(members))

    # ── Delta Sync ──────────────────────────────────────────────
    async def sync_delta(self, since_str: str):
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        result = await self.repo.sync_delta(since)
        result.items = [RateZoneSummarySchema.model_validate(r) for r in result.items]
        return result

    # ── Update ──────────────────────────────────────────────────
    async def update(
        self, zone_id: int, payload: RateZoneUpdateRequest, actor_user_id: int | None = None
    ) -> RateZoneResponseSchema:
        data = payload.model_dump(exclude_unset=True)
        current = await self.repo.get_header(zone_id)
        if not current:
            raise NotFoundException(_LABEL)
        if "rate_group_id" in data:
            await self._validate_group(data["rate_group_id"])
            # 스코프 이동(그룹↔그룹/글로벌) 시 대상 스코프에서도 "원자당 존 1개" 불변식 유지
            if data["rate_group_id"] != current.rate_group_id:
                existing_members = await self.repo.list_members(zone_id)
                members_data = [
                    {"zip_code": m.zip_code, "city": m.city, "state": m.state}
                    for m in existing_members
                ]
                await self._check_atom_conflicts(zone_id, data["rate_group_id"], members_data)
        # kind 변경은 멤버가 비어있을 때만 — 멤버가 있으면 원자 타입과 어긋남
        if "kind" in data and data["kind"] != current.kind:
            existing_members = await self.repo.list_members(zone_id)
            if existing_members:
                raise AppException(
                    code="ZONE_KIND_LOCKED",
                    message="멤버가 있는 존의 종류는 변경할 수 없습니다 — 멤버를 비운 뒤 변경하세요.",
                    status_code=409,
                )
        zone = await self.repo.update_header(zone_id, data, actor_user_id=actor_user_id)
        if not zone:
            raise NotFoundException(_LABEL)
        await emit_entity_event("rate_zone.updated", self.team_id,
                                {"rateZoneId": zone_id}, actor_user_id)
        return RateZoneResponseSchema.model_validate(zone)

    async def replace_members(
        self, zone_id: int, payload: RateZoneMembersReplaceRequest, actor_user_id: int | None = None
    ) -> RateZoneMembersResponseSchema:
        zone = await self.repo.get_header(zone_id)
        if not zone:
            raise NotFoundException(_LABEL)
        members_data = [m.model_dump() for m in payload.members]
        self._check_kind_match(zone.kind, members_data)
        await self._check_atom_conflicts(zone_id, zone.rate_group_id, members_data)
        rows = await self.repo.replace_members(zone_id, members_data, actor_user_id=actor_user_id)
        members = [RateZoneMemberResponseSchema.model_validate(r) for r in rows]
        await emit_entity_event("rate_zone.updated", self.team_id,
                                {"rateZoneId": zone_id}, actor_user_id)
        return RateZoneMembersResponseSchema(zone_id=zone_id, members=members, count=len(members))

    async def add_members_by_city(
        self, zone_id: int, city: str, state: str, actor_user_id: int | None = None
    ) -> RateZoneMembersResponseSchema:
        """(city, state) 의 모든 zip 을 zip 마스터에서 찾아 기존 zip 멤버에 합집합 추가.

        **ZIP존 전용** — 도시→zip 확장 단축키. 도시존은 도시 멤버를 직접 추가해야 한다.
        """
        zone = await self.repo.get_header(zone_id)
        if not zone:
            raise NotFoundException(_LABEL)
        if zone.kind != ZoneKind.ZIP:
            raise AppException(
                code="ZONE_KIND_MISMATCH",
                message="'도시로 추가(zip 확장)'는 ZIP존 전용입니다 — 도시존에는 도시 멤버를 직접 추가하세요.",
                status_code=422,
            )
        new_zips = await ZipCodeRepository(self.db).find_zips_by_city(city, state)
        if not new_zips:
            raise AppException(
                code="NO_ZIPS_FOUND",
                message=f"'{city}, {state}' 에 해당하는 우편번호가 zip 마스터에 없습니다.",
                status_code=404,
            )
        existing_rows = await self.repo.list_members(zone_id)
        existing_zips = {r.zip_code for r in existing_rows if r.zip_code}
        city_members = [
            {"city": r.city, "state": r.state} for r in existing_rows if r.city
        ]
        union = sorted(existing_zips | set(new_zips))
        members_data = [{"zip_code": z} for z in union] + city_members
        await self._check_atom_conflicts(zone_id, zone.rate_group_id, members_data)
        rows = await self.repo.replace_members(zone_id, members_data, actor_user_id=actor_user_id)
        members = [RateZoneMemberResponseSchema.model_validate(r) for r in rows]
        await emit_entity_event("rate_zone.updated", self.team_id,
                                {"rateZoneId": zone_id}, actor_user_id)
        return RateZoneMembersResponseSchema(zone_id=zone_id, members=members, count=len(members))

    # ── Delete ──────────────────────────────────────────────────
    async def delete(
        self, zone_id: int, actor_user_id: int | None = None
    ) -> RateZoneDeleteResponseSchema:
        zone = await self.repo.get_header(zone_id)
        if not zone:
            raise NotFoundException(_LABEL)
        await self.repo.soft_deactivate_by_id(zone_id, actor_user_id=actor_user_id)
        await emit_entity_event("rate_zone.deleted", self.team_id,
                                {"rateZoneId": zone_id}, actor_user_id)
        return RateZoneDeleteResponseSchema(id=zone_id, deleted=True, soft_deleted=True)
