# src/service_area/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import SERVICE_AREA_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from service_area.service import ServiceAreaService
from service_area.schemas.request import ServiceAreaCreateRequest, PaginateServiceAreaRequest
from service_area.schemas.response import ServiceAreaResponseSchema, ServiceAreaDeleteResponseSchema

router = APIRouter(prefix="/api/v1/service-areas", tags=["service-areas"])


@router.post("", response_model=ServiceAreaResponseSchema)
async def create_service_area(
    body: ServiceAreaCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SERVICE_AREA_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """영업권역 선언 추가 (STATE/COUNTY/CITY/ZIP3) — 쓰기 권한 필요."""
    return await ServiceAreaService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[ServiceAreaResponseSchema])
async def list_service_areas(
    request: PaginateServiceAreaRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """영업권역 선언 목록 (커서 페이지네이션)."""
    return await ServiceAreaService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[ServiceAreaResponseSchema])
async def sync_service_areas(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Service Area Delta Sync (WS reconnect catch-up)."""
    return await ServiceAreaService(db, team_id).sync_delta(since)


@router.delete("/{area_id}", response_model=ServiceAreaDeleteResponseSchema)
async def delete_service_area(
    area_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SERVICE_AREA_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """영업권역 선언 삭제(소프트)."""
    return await ServiceAreaService(db, team_id).delete(area_id, actor_user_id=int(me.id))
