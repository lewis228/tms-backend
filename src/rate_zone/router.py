# src/rate_zone/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import RATE_ZONE_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from rate_zone.service import RateZoneService
from rate_zone.schemas.request import (
    RateZoneCreateRequest, RateZoneUpdateRequest, PaginateRateZoneRequest,
    RateZoneMembersReplaceRequest, AddMembersByCityRequest,
)
from rate_zone.schemas.response import (
    RateZoneResponseSchema, RateZoneSummarySchema, RateZoneDeleteResponseSchema, RateZoneMembersResponseSchema,
)

router = APIRouter(prefix="/api/v1/rate-zones", tags=["rate-zones"])


@router.post("", response_model=RateZoneResponseSchema)
async def create_rate_zone(
    body: RateZoneCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_ZONE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Zone 생성(멤버 인라인 동시 생성 가능) — 쓰기 권한 필요."""
    return await RateZoneService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[RateZoneSummarySchema])
async def list_rate_zones(
    request: PaginateRateZoneRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Zone 목록(커서 페이징, 헤더만)."""
    return await RateZoneService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[RateZoneSummarySchema])
async def sync_rate_zones(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Zone Delta Sync."""
    return await RateZoneService(db, team_id).sync_delta(since)


@router.get("/{zone_id}", response_model=RateZoneResponseSchema)
async def get_rate_zone(
    zone_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Zone 단건 조회(멤버 포함)."""
    return await RateZoneService(db, team_id).get(zone_id)


@router.put("/{zone_id}", response_model=RateZoneResponseSchema)
async def update_rate_zone(
    zone_id: int,
    body: RateZoneUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_ZONE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Zone 헤더 수정 — 쓰기 권한 필요."""
    return await RateZoneService(db, team_id).update(zone_id, body, actor_user_id=int(me.id))


@router.delete("/{zone_id}", response_model=RateZoneDeleteResponseSchema)
async def delete_rate_zone(
    zone_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_ZONE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Zone 삭제(소프트)."""
    return await RateZoneService(db, team_id).delete(zone_id, actor_user_id=int(me.id))


# ── 멤버(zip/city) 관리 ─────────────────────────────────────────
@router.get("/{zone_id}/members", response_model=RateZoneMembersResponseSchema)
async def list_rate_zone_members(
    zone_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Zone 의 zip/city 멤버 목록."""
    return await RateZoneService(db, team_id).list_members(zone_id)


@router.put("/{zone_id}/members", response_model=RateZoneMembersResponseSchema)
async def replace_rate_zone_members(
    zone_id: int,
    body: RateZoneMembersReplaceRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_ZONE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Zone 의 멤버 전체 교체(PUT). 지도 백필/Excel import 결과 반영용."""
    return await RateZoneService(db, team_id).replace_members(zone_id, body, actor_user_id=int(me.id))


@router.post("/{zone_id}/members/by-city", response_model=RateZoneMembersResponseSchema)
async def add_rate_zone_members_by_city(
    zone_id: int,
    body: AddMembersByCityRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_ZONE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """도시(city+state)의 모든 zip 을 zip 마스터에서 찾아 멤버에 합집합 추가."""
    return await RateZoneService(db, team_id).add_members_by_city(
        zone_id, body.city, body.state, actor_user_id=int(me.id)
    )
