# src/rate_point/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import RATE_POINT_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from rate_point.service import RatePointService
from rate_point.schemas.request import (
    RatePointCreateRequest, RatePointUpdateRequest, PaginateRatePointRequest,
    RatePointBulkCreateRequest, RatePointBulkUpdateRequest, RatePointBulkDeleteRequest,
)
from rate_point.schemas.response import (
    RatePointResponseSchema, RatePointDeleteResponseSchema,
    RatePointBulkCreateResponseSchema, RatePointBulkUpdateResponseSchema, RatePointBulkDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/rate-points", tags=["rate-points"])


# ── 단건 CRUD ───────────────────────────────────────────────────
@router.post("", response_model=RatePointResponseSchema)
async def create_rate_point(
    body: RatePointCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_POINT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Point(Terminal/Yard) 생성 — 쓰기 권한 필요."""
    return await RatePointService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[RatePointResponseSchema])
async def list_rate_points(
    request: PaginateRatePointRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Point 목록(커서 페이징)."""
    return await RatePointService(db, team_id).list_paginated(request)


# /sync 는 /{point_id} 보다 먼저 정의해야 "sync" 가 point_id 로 파싱되지 않음
@router.get("/sync", response_model=SyncResponse[RatePointResponseSchema])
async def sync_rate_points(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Point Delta Sync."""
    return await RatePointService(db, team_id).sync_delta(since)


@router.get("/{point_id}", response_model=RatePointResponseSchema)
async def get_rate_point(
    point_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Point 단건 조회(활성만)."""
    return await RatePointService(db, team_id).get(point_id)


@router.put("/{point_id}", response_model=RatePointResponseSchema)
async def update_rate_point(
    point_id: int,
    body: RatePointUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_POINT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Point 수정 — 쓰기 권한 필요."""
    return await RatePointService(db, team_id).update(point_id, body, actor_user_id=int(me.id))


@router.delete("/{point_id}", response_model=RatePointDeleteResponseSchema)
async def delete_rate_point(
    point_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_POINT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Point 삭제(소프트)."""
    return await RatePointService(db, team_id).delete(point_id, actor_user_id=int(me.id))


# ── 벌크 CRUD ───────────────────────────────────────────────────
@router.post("/bulk/create", response_model=RatePointBulkCreateResponseSchema)
async def create_rate_points_bulk(
    body: RatePointBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_POINT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Point 벌크 생성 (최대 100개, 전체 성공 or 전체 실패)."""
    return await RatePointService(db, team_id).create_bulk(body, actor_user_id=int(me.id))


@router.post("/bulk/update", response_model=RatePointBulkUpdateResponseSchema)
async def update_rate_points_bulk(
    body: RatePointBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_POINT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Point 벌크 수정 (최대 100개)."""
    return await RatePointService(db, team_id).update_bulk(body, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=RatePointBulkDeleteResponseSchema)
async def delete_rate_points_bulk(
    body: RatePointBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_POINT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Point 벌크 삭제 (최대 100개, 소프트)."""
    return await RatePointService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))
