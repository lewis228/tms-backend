"""Notifications 라우터 — 인증 사용자 본인 것만."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import CurrentUser, DB, DBReadOnly, TenantID
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.notifications.repository import NotificationRepository
from app.domains.notifications.schema import (
    NotificationCreateRequest,
    NotificationResponse,
)
from app.domains.notifications.service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _svc(db, *, tenant_id: str) -> NotificationService:
    return NotificationService(NotificationRepository(db, tenant_id=tenant_id), tenant_id)


@router.get("", response_model=PagedResponse[NotificationResponse])
async def list_notifications(
    user: CurrentUser,
    tenant_id: TenantID,
    db: DBReadOnly,
    params: Annotated[PageParams, Depends(page_params)],
    unread_only: bool = Query(False, alias="unreadOnly"),
):
    items, total = await _svc(db, tenant_id=tenant_id).list_for_user(
        user.user_id, params, unread_only=unread_only
    )
    return PagedResponse.of(
        [NotificationResponse.model_validate(i) for i in items], total, params
    )


@router.get("/unread-count")
async def unread_count(user: CurrentUser, tenant_id: TenantID, db: DBReadOnly):
    cnt = await _svc(db, tenant_id=tenant_id).count_unread(user.user_id)
    return {"count": cnt}


@router.post("/{id}/read", response_model=NotificationResponse)
async def mark_read(id: str, user: CurrentUser, tenant_id: TenantID, db: DB):
    return NotificationResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).mark_read(id, user.user_id)
    )


@router.post("/read-all")
async def mark_all_read(user: CurrentUser, tenant_id: TenantID, db: DB):
    n = await _svc(db, tenant_id=tenant_id).mark_all_read(user.user_id)
    return {"updated": n}


@router.post("", response_model=NotificationResponse, status_code=201)
async def create_notification(
    payload: NotificationCreateRequest, tenant_id: TenantID, db: DB
):
    return NotificationResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).create(payload)
    )
