# src/driver_rate_assignment/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import DRIVER_RATE_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from driver_rate_assignment.service import DriverRateAssignmentService
from driver_rate_assignment.schemas.request import (
    DriverRateAssignmentCreateRequest, DriverRateAssignmentUpdateRequest,
    PaginateDriverRateAssignmentRequest,
)
from driver_rate_assignment.schemas.response import (
    DriverRateAssignmentResponseSchema, DriverRateAssignmentDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/driver-rate-assignments", tags=["driver-rate-assignments"])


@router.post("", response_model=DriverRateAssignmentResponseSchema)
async def create_driver_rate_assignment(
    body: DriverRateAssignmentCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """드라이버↔요율그룹 배정 생성 — 쓰기 권한 필요."""
    return await DriverRateAssignmentService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[DriverRateAssignmentResponseSchema])
async def list_driver_rate_assignments(
    request: PaginateDriverRateAssignmentRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """드라이버 요율 배정 목록(커서 페이징)."""
    return await DriverRateAssignmentService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[DriverRateAssignmentResponseSchema])
async def sync_driver_rate_assignments(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """드라이버 요율 배정 Delta Sync."""
    return await DriverRateAssignmentService(db, team_id).sync_delta(since)


@router.get("/{assignment_id}", response_model=DriverRateAssignmentResponseSchema)
async def get_driver_rate_assignment(
    assignment_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """드라이버 요율 배정 단건 조회(활성만)."""
    return await DriverRateAssignmentService(db, team_id).get(assignment_id)


@router.put("/{assignment_id}", response_model=DriverRateAssignmentResponseSchema)
async def update_driver_rate_assignment(
    assignment_id: int,
    body: DriverRateAssignmentUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """드라이버 요율 배정 수정 — 쓰기 권한 필요."""
    return await DriverRateAssignmentService(db, team_id).update(assignment_id, body, actor_user_id=int(me.id))


@router.delete("/{assignment_id}", response_model=DriverRateAssignmentDeleteResponseSchema)
async def delete_driver_rate_assignment(
    assignment_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """드라이버 요율 배정 삭제(소프트)."""
    return await DriverRateAssignmentService(db, team_id).delete(assignment_id, actor_user_id=int(me.id))
