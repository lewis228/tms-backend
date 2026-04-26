# src/driver_mobile/router.py
"""Driver mobile 전용 라우터 — DRIVER role 만 호출.

데이터 모델은 다른 도메인 (Leg/File/User) 재사용. 라우터만 분리.
실제 비즈니스 로직 (today_legs, checkpoint, location batch, push token) 은
service 계층에서 이미 정의된 LegService 등을 호출.
"""
from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.dependencies.guards import permission_guard  # noqa: F401  (DRIVER role 만 통과)
from tenant.dependencies.get_tenant_scope import get_tenant_scope
from user.dependencies.current_user import get_current_user
from user.const.roles import RolesEnum
from user.schemas.response import UserResponseSchema

from driver_mobile.schemas.request import (
    CheckpointRequest, LocationBatchRequest, PushTokenRequest,
    FirstPasswordChangeRequest,
)
from driver_mobile.schemas.response import TodayTasksResponse, PushTokenResponse
from leg.schemas.response import LegResponseSchema

router = APIRouter(prefix="/driver", tags=["driver_mobile"])

ALLOWED_DOCUMENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf",
}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def require_driver(me: UserResponseSchema = Depends(get_current_user)) -> UserResponseSchema:
    if str(getattr(me, "role", "")) != RolesEnum.DRIVER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN_ROLE",
                    "message": "DRIVER 만 호출할 수 있습니다."},
        )
    return me


@router.get("/tasks/today", response_model=TodayTasksResponse)
async def tasks_today(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """오늘 할당된 Leg 목록 — TODO: leg.service 호출"""
    return TodayTasksResponse(legs=[])


@router.post("/legs/{leg_id}/checkpoint", response_model=LegResponseSchema)
async def checkpoint(
    leg_id: int,
    body: CheckpointRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """Leg 상태 전이 (PENDING → IN_TRANSIT 등) — TODO: leg.service 호출"""
    raise HTTPException(status_code=501, detail="not implemented")


@router.post("/location", status_code=204)
async def location_batch(
    body: LocationBatchRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """GPS batch — TODO: 별도 location_ping 도메인"""
    return None


@router.post("/push-tokens", response_model=PushTokenResponse, status_code=201)
async def upsert_push_token(
    body: PushTokenRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """FCM/APNs 토큰 등록 — TODO: 별도 push_token 도메인"""
    raise HTTPException(status_code=501, detail="not implemented")


@router.post(
    "/legs/{leg_id}/documents",
    status_code=201,
)
async def upload_leg_document(
    leg_id: int,
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()],
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    tenant_id: int = Depends(get_tenant_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """POD/Receipt 등 leg 첨부 — multipart 1회. TODO: file.service 통합"""
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail={
            "code": "ERR_FILE_TYPE",
            "message": f"Unsupported content_type: {file.content_type}"})
    body = await file.read()
    if not body:
        raise HTTPException(status_code=400, detail={"code": "ERR_FILE_EMPTY"})
    if len(body) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=400, detail={
            "code": "ERR_FILE_TOO_LARGE",
            "message": f"max {MAX_DOCUMENT_BYTES} bytes"})
    raise HTTPException(status_code=501, detail="not implemented")


@router.patch("/me/password")
async def change_first_password(
    body: FirstPasswordChangeRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    db: AsyncSession = Depends(get_write_db),
):
    """첫 로그인 비밀번호 변경 — must_change_password 해제"""
    raise HTTPException(status_code=501, detail="not implemented")
