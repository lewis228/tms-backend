# src/leg/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import LEG_WRITE
from rbac.dependencies.guards import permission_guard
from tenant.dependencies.get_tenant_scope import get_tenant_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from leg.service import LegService
from leg.schemas.request import (
    LegCreateRequest, LegUpdateRequest, PaginateLegRequest,
    LegBulkCreateRequest, LegBulkUpdateRequest, LegBulkDeleteRequest,
)
from leg.schemas.response import (
    LegResponseSchema, LegDeleteResponseSchema,
    LegBulkCreateResponseSchema, LegBulkUpdateResponseSchema, LegBulkDeleteResponseSchema,
)

router = APIRouter(prefix="/legs", tags=["legs"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=LegResponseSchema)
async def create_leg(
    body: LegCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 생성
    - 쓰기 권한 필요
    """
    return await LegService(db, tenant_id).create(
        body,
        actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[LegResponseSchema])
async def list_legs(
    request: PaginateLegRequest = Depends(),
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 목록(커서 페이징)
    - 기본 활성만; include_inactive=True 로 비활성 포함
    - 정렬/필터는 DTO의 order__/where__ 파라미터 사용
    """
    return await LegService(db, tenant_id).list_paginated(request)


# ═══════════════════════════════════════════════════════════════
# Delta Sync
# /{leg_id}보다 먼저 정의해야 "sync"가 leg_id로 파싱되지 않음
# ═══════════════════════════════════════════════════════════════

@router.get("/sync", response_model=SyncResponse[LegResponseSchema])
async def sync_legs(
    since: str,
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 Delta Sync

    - since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환
    """
    return await LegService(db, tenant_id).sync_delta(since)


@router.get("/{leg_id}", response_model=LegResponseSchema)
async def get_leg(
    leg_id: int,
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 단건 조회(활성만)
    """
    return await LegService(db, tenant_id).get(leg_id)


@router.put("/{leg_id}", response_model=LegResponseSchema)
async def update_leg(
    leg_id: int,
    body: LegUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 수정(활성만)
    - 쓰기 권한 필요
    """
    return await LegService(db, tenant_id).update(
        leg_id,
        body,
        actor_user_id=int(me.id),
    )


@router.delete("/{leg_id}", response_model=LegDeleteResponseSchema)
async def delete_leg(
    leg_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    """
    return await LegService(db, tenant_id).delete(
        leg_id,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 벌크 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/bulk/create", response_model=LegBulkCreateResponseSchema)
async def create_legs_bulk(
    body: LegBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 생성 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 부분 성공 허용
    """
    return await LegService(db, tenant_id).create_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/update", response_model=LegBulkUpdateResponseSchema)
async def update_legs_bulk(
    body: LegBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 수정 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 존재하지 않는 ID는 실패 처리
    """
    return await LegService(db, tenant_id).update_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/delete", response_model=LegBulkDeleteResponseSchema)
async def delete_legs_bulk(
    body: LegBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 삭제 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 하드 삭제 우선, FK 제약 시 소프트 삭제
    """
    return await LegService(db, tenant_id).delete_bulk(
        body,
        actor_user_id=int(me.id),
    )