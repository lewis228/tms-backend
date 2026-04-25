"""Driver 모바일 전용 라우터 — DRIVER 만 호출.

데이터 모델은 다른 도메인 재사용 (Leg / File / User), 라우터만 분리.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.core.dependencies import DB, CurrentUser, DBReadOnly, TenantID, require_role
from app.core.exceptions import ValidationError
from app.domains.driver.repository import DriverMobileRepository
from app.domains.driver.schema import (
    CheckpointRequest,
    FirstPasswordChangeRequest,
    LocationBatchRequest,
    PushTokenRequest,
    PushTokenResponse,
    TodayTasksResponse,
)
from app.domains.driver.service import DriverMobileService
from app.domains.files.schema import FileResponse
from app.domains.legs.repository import LegRepository
from app.domains.legs.schema import LegResponse
from app.domains.users.repository import UserRepository
from app.domains.users.schema import PasswordChangeRequest, UserResponse
from app.domains.users.service import UserService

router = APIRouter(
    prefix="/api/v1/driver",
    tags=["driver"],
    dependencies=[require_role("DRIVER")],
)

# 모바일 documents 업로드 한도. POD/RECEIPT 사진+PDF 가정.
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_DOCUMENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
}


def _svc(db, *, tenant_id: str) -> DriverMobileService:
    return DriverMobileService(
        DriverMobileRepository(db, tenant_id=tenant_id),
        LegRepository(db, tenant_id=tenant_id),
        tenant_id,
    )


@router.get("/tasks/today", response_model=TodayTasksResponse)
async def tasks_today(user: CurrentUser, tenant_id: TenantID, db: DBReadOnly):
    legs = await _svc(db, tenant_id=tenant_id).today_legs(user.user_id)
    return TodayTasksResponse(legs=[LegResponse.model_validate(l) for l in legs])


@router.post("/legs/{leg_id}/checkpoint", response_model=LegResponse)
async def checkpoint(
    leg_id: str,
    payload: CheckpointRequest,
    user: CurrentUser,
    tenant_id: TenantID,
    db: DB,
):
    leg = await _svc(db, tenant_id=tenant_id).checkpoint_leg(
        leg_id,
        payload.target,
        user_id=user.user_id,
        failure_reason=payload.failure_reason,
    )
    return LegResponse.model_validate(leg)


@router.post("/location", status_code=204)
async def location_batch(
    payload: LocationBatchRequest, user: CurrentUser, tenant_id: TenantID, db: DB
):
    if not payload.pings:
        raise ValidationError("pings empty")
    pings = [p.model_dump() for p in payload.pings]
    await _svc(db, tenant_id=tenant_id).add_location_pings(
        user_id=user.user_id, pings=pings
    )


@router.post("/push-tokens", response_model=PushTokenResponse, status_code=201)
async def upsert_push_token(
    payload: PushTokenRequest, user: CurrentUser, tenant_id: TenantID, db: DB
):
    row = await _svc(db, tenant_id=tenant_id).upsert_push_token(
        user_id=user.user_id, platform=payload.platform, token=payload.token
    )
    return PushTokenResponse.model_validate(row)


@router.post(
    "/legs/{leg_id}/documents",
    response_model=FileResponse,
    status_code=201,
)
async def upload_leg_document(
    leg_id: str,
    user: CurrentUser,
    tenant_id: TenantID,
    db: DB,
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()],
):
    """POD / RECEIPT 등 leg 첨부 — Driver 가 모바일에서 직접 멀티파트 업로드.

    검증:
    - content_type 화이트리스트 (image/* + pdf). 임의 실행파일/HTML 차단.
    - 본문 크기 ≤ MAX_DOCUMENT_BYTES (10MB). OOM 방지.
    """
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_DOCUMENT_TYPES:
        raise ValidationError(
            f"Unsupported content_type: {content_type}",
            code="ERR_FILE_TYPE",
        )
    body = await file.read()
    if not body:
        raise ValidationError("Empty file", code="ERR_FILE_EMPTY")
    if len(body) > MAX_DOCUMENT_BYTES:
        raise ValidationError(
            f"File too large: {len(body)} bytes (max {MAX_DOCUMENT_BYTES})",
            code="ERR_FILE_TOO_LARGE",
        )
    f = await _svc(db, tenant_id=tenant_id).attach_leg_document(
        leg_id=leg_id,
        user_id=user.user_id,
        kind=kind,
        filename=file.filename or "document",
        content_type=content_type,
        body=body,
    )
    return FileResponse.model_validate(f)


@router.patch("/me/password", response_model=UserResponse)
async def change_first_password(
    payload: FirstPasswordChangeRequest,
    user: CurrentUser,
    tenant_id: TenantID,
    db: DB,
):
    """첫 로그인 시 비밀번호 강제 변경 — must_change_password 플래그 해제."""
    user_repo = UserRepository(db, tenant_id=tenant_id)
    user_svc = UserService(user_repo)
    me = await user_svc.get(user.user_id)
    if not me.must_change_password:
        raise ValidationError("Password change not required", code="ERR_PW_NOT_REQUIRED")
    updated = await user_svc.change_password(
        me, PasswordChangeRequest(new_password=payload.new_password), force=True
    )
    return UserResponse.model_validate(updated)
