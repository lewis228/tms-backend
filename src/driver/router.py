# src/driver/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import DRIVER_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from driver.service import DriverService
from driver.schemas.request import (
    DriverCreateRequest, DriverUpdateRequest, PaginateDriverRequest,
    DriverBulkCreateRequest, DriverBulkUpdateRequest, DriverBulkDeleteRequest,
)
from driver.schemas.response import (
    DriverResponseSchema, DriverDeleteResponseSchema,
    DriverBulkCreateResponseSchema, DriverBulkUpdateResponseSchema, DriverBulkDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/drivers", tags=["drivers"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=DriverResponseSchema)
async def create_driver(
    body: DriverCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 생성
    - 쓰기 권한 필요
    """
    return await DriverService(db, team_id).create(
        body,
        actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[DriverResponseSchema])
async def list_drivers(
    request: PaginateDriverRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 목록(커서 페이징)
    - 기본 활성만; include_inactive=True 로 비활성 포함
    - 정렬/필터는 DTO의 order__/where__ 파라미터 사용
    """
    return await DriverService(db, team_id).list_paginated(request)


# ═══════════════════════════════════════════════════════════════
# Delta Sync
# /{driver_id}보다 먼저 정의해야 "sync"가 driver_id로 파싱되지 않음
# ═══════════════════════════════════════════════════════════════

@router.get("/sync", response_model=SyncResponse[DriverResponseSchema])
async def sync_drivers(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 Delta Sync

    - since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환
    """
    return await DriverService(db, team_id).sync_delta(since)


@router.get("/{driver_id}", response_model=DriverResponseSchema)
async def get_driver(
    driver_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 단건 조회(활성만)
    """
    return await DriverService(db, team_id).get(driver_id)


@router.put("/{driver_id}", response_model=DriverResponseSchema)
async def update_driver(
    driver_id: int,
    body: DriverUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 수정(활성만)
    - 쓰기 권한 필요
    """
    return await DriverService(db, team_id).update(
        driver_id,
        body,
        actor_user_id=int(me.id),
    )


@router.delete("/{driver_id}", response_model=DriverDeleteResponseSchema)
async def delete_driver(
    driver_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    """
    return await DriverService(db, team_id).delete(
        driver_id,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 벌크 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/bulk/create", response_model=DriverBulkCreateResponseSchema)
async def create_drivers_bulk(
    body: DriverBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 생성 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 부분 성공 허용
    """
    return await DriverService(db, team_id).create_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/update", response_model=DriverBulkUpdateResponseSchema)
async def update_drivers_bulk(
    body: DriverBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 수정 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 존재하지 않는 ID는 실패 처리
    """
    return await DriverService(db, team_id).update_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/delete", response_model=DriverBulkDeleteResponseSchema)
async def delete_drivers_bulk(
    body: DriverBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DRIVER_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 삭제 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 하드 삭제 우선, FK 제약 시 소프트 삭제
    """
    return await DriverService(db, team_id).delete_bulk(
        body,
        actor_user_id=int(me.id),
    )