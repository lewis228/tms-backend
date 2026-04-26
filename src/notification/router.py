# src/notification/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import NOTIFICATION_WRITE
from rbac.dependencies.guards import permission_guard
from tenant.dependencies.get_tenant_scope import get_tenant_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from notification.service import NotificationService
from notification.schemas.request import (
    NotificationCreateRequest, NotificationUpdateRequest, PaginateNotificationRequest,
    NotificationBulkCreateRequest, NotificationBulkUpdateRequest, NotificationBulkDeleteRequest,
)
from notification.schemas.response import (
    NotificationResponseSchema, NotificationDeleteResponseSchema,
    NotificationBulkCreateResponseSchema, NotificationBulkUpdateResponseSchema, NotificationBulkDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# ═══════════════════════════════════════════════════════════════
# 단건 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("", response_model=NotificationResponseSchema)
async def create_notification(
    body: NotificationCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(NOTIFICATION_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 생성
    - 쓰기 권한 필요
    """
    return await NotificationService(db, tenant_id).create(
        body,
        actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[NotificationResponseSchema])
async def list_notifications(
    request: PaginateNotificationRequest = Depends(),
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 목록(커서 페이징)
    - 기본 활성만; include_inactive=True 로 비활성 포함
    - 정렬/필터는 DTO의 order__/where__ 파라미터 사용
    """
    return await NotificationService(db, tenant_id).list_paginated(request)


# ═══════════════════════════════════════════════════════════════
# Delta Sync
# /{notification_id}보다 먼저 정의해야 "sync"가 notification_id로 파싱되지 않음
# ═══════════════════════════════════════════════════════════════

@router.get("/sync", response_model=SyncResponse[NotificationResponseSchema])
async def sync_notifications(
    since: str,
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 Delta Sync

    - since 이후 변경된 활성 아이템 + soft-delete된 아이템 ID 반환
    """
    return await NotificationService(db, tenant_id).sync_delta(since)


@router.get("/{notification_id}", response_model=NotificationResponseSchema)
async def get_notification(
    notification_id: int,
    _1: None = Depends(access_token),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """
    거래처 단건 조회(활성만)
    """
    return await NotificationService(db, tenant_id).get(notification_id)


@router.put("/{notification_id}", response_model=NotificationResponseSchema)
async def update_notification(
    notification_id: int,
    body: NotificationUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(NOTIFICATION_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 수정(활성만)
    - 쓰기 권한 필요
    """
    return await NotificationService(db, tenant_id).update(
        notification_id,
        body,
        actor_user_id=int(me.id),
    )


@router.delete("/{notification_id}", response_model=NotificationDeleteResponseSchema)
async def delete_notification(
    notification_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(NOTIFICATION_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 삭제
    - 하드 삭제 우선, FK 제약 시 소프트 비활성화
    """
    return await NotificationService(db, tenant_id).delete(
        notification_id,
        actor_user_id=int(me.id),
    )


# ═══════════════════════════════════════════════════════════════
# 벌크 CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/bulk/create", response_model=NotificationBulkCreateResponseSchema)
async def create_notifications_bulk(
    body: NotificationBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(NOTIFICATION_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 생성 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 부분 성공 허용
    """
    return await NotificationService(db, tenant_id).create_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/update", response_model=NotificationBulkUpdateResponseSchema)
async def update_notifications_bulk(
    body: NotificationBulkUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(NOTIFICATION_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 수정 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 존재하지 않는 ID는 실패 처리
    """
    return await NotificationService(db, tenant_id).update_bulk(
        body,
        actor_user_id=int(me.id),
    )


@router.post("/bulk/delete", response_model=NotificationBulkDeleteResponseSchema)
async def delete_notifications_bulk(
    body: NotificationBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(NOTIFICATION_WRITE)),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """
    거래처 벌크 삭제 (최대 100개)
    - 개별 항목별 성공/실패 처리
    - 하드 삭제 우선, FK 제약 시 소프트 삭제
    """
    return await NotificationService(db, tenant_id).delete_bulk(
        body,
        actor_user_id=int(me.id),
    )