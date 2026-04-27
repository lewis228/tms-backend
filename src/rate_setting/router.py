# src/rate_setting/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import RATE_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from rate_setting.service import RateSettingService
from rate_setting.schemas.request import (
    RateSettingCreateRequest, RateSettingUpdateRequest, PaginateRateSettingRequest,
    RateSettingBulkCreateRequest, RateSettingBulkUpdateRequest, RateSettingBulkDeleteRequest,
)
from rate_setting.schemas.response import (
    RateSettingResponseSchema, RateSettingDeleteResponseSchema,
    RateSettingBulkCreateResponseSchema, RateSettingBulkUpdateResponseSchema, RateSettingBulkDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/rate-settings", tags=["rate-settings"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=RateSettingResponseSchema)
async def create_rate_setting(
    body: RateSettingCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 생성
    - 쓰기 권한 필요
    """
    return await RateSettingService(db, team_id).create(
        body,
        actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[RateSettingResponseSchema])
async def list_rate_settings(
    request: PaginateRateSettingRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 목록(커서 페이징)
    - 기본 활성만; include_inactive=True 로 비활성 포함
    - 정렬/필터는 DTO의 order__/where__ 파라미터 사용
    """
    return await RateSettingService(db, team_id).list_paginated(request)


# ═══════════════════════════════════════════════════════════════
# Delta Sync
# /{rate_setting_id}보다 먼저 정의해야 "sync"가 rate_setting_id로 파싱되지 않음
# ═══════════════════════════════════════════════════════════════

@router.get("/sync", response_model=SyncResponse[RateSettingResponseSchema])
async def sync_rate_settings(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 Delta Sync

    - since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환
    """
    return await RateSettingService(db, team_id).sync_delta(since)


@router.get("/{rate_setting_id}", response_model=RateSettingResponseSchema)
async def get_rate_setting(
    rate_setting_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 단건 조회(활성만)
    """
    return await RateSettingService(db, team_id).get(rate_setting_id)


@router.put("/{rate_setting_id}", response_model=RateSettingResponseSchema)
async def update_rate_setting(
    rate_setting_id: int,
    body: RateSettingUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 수정(활성만)
    - 쓰기 권한 필요
    """
    return await RateSettingService(db, team_id).update(
        rate_setting_id,
        body,
        actor_user_id=int(me.id),
    )


@router.delete("/{rate_setting_id}", response_model=RateSettingDeleteResponseSchema)
async def delete_rate_setting(
    rate_setting_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    """
    return await RateSettingService(db, team_id).delete(
        rate_setting_id,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 벌크 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/bulk/create", response_model=RateSettingBulkCreateResponseSchema)
async def create_rate_settings_bulk(
    body: RateSettingBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 생성 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 부분 성공 허용
    """
    return await RateSettingService(db, team_id).create_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/update", response_model=RateSettingBulkUpdateResponseSchema)
async def update_rate_settings_bulk(
    body: RateSettingBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 수정 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 존재하지 않는 ID는 실패 처리
    """
    return await RateSettingService(db, team_id).update_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/delete", response_model=RateSettingBulkDeleteResponseSchema)
async def delete_rate_settings_bulk(
    body: RateSettingBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 삭제 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 하드 삭제 우선, FK 제약 시 소프트 삭제
    """
    return await RateSettingService(db, team_id).delete_bulk(
        body,
        actor_user_id=int(me.id),
    )