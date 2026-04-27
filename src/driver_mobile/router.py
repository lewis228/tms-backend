# src/driver_mobile/router.py
"""Driver mobile 전용 라우터 — DRIVER role 만 호출."""
from __future__ import annotations
from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from common.exceptions.base import NotFoundException
from common.const.settings import settings
from database.dependencies import get_read_db, get_write_db
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.const.roles import RolesEnum
from user.schemas.response import UserResponseSchema

from driver_mobile.schemas.request import (
    CheckpointRequest, LocationBatchRequest, PushTokenRequest,
    FirstPasswordChangeRequest,
)
from driver_mobile.schemas.response import TodayTasksResponse, PushTokenResponse  # noqa: F401
from driver_mobile.service import DriverMobileService
from leg.schemas.response import LegResponseSchema

router = APIRouter(prefix="/api/v1/driver", tags=["driver_mobile"])

ALLOWED_DOCUMENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf",
}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def require_driver(me: UserResponseSchema = Depends(get_current_user)) -> UserResponseSchema:
    role = getattr(me, "role", None)
    role_value = getattr(role, "value", role)  # RolesEnum 또는 str 모두 처리
    if role_value != RolesEnum.DRIVER.value:
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
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """오늘 할당된 Leg 목록 (PENDING/IN_TRANSIT)."""
    legs = await DriverMobileService(db, team_id).today_legs(int(me.id))
    return TodayTasksResponse(
        legs=[LegResponseSchema.model_validate(l) for l in legs],
    )


@router.post("/legs/{leg_id}/checkpoint", response_model=LegResponseSchema)
async def checkpoint(
    leg_id: int,
    body: CheckpointRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """Leg 상태 전이 (PENDING → IN_TRANSIT 등). 본인 leg 검증 + leg.service.transition."""
    return await DriverMobileService(db, team_id).checkpoint_leg(
        leg_id, body.target,
        user_id=int(me.id), failure_reason=body.failure_reason,
    )


@router.post("/location", status_code=204)
async def location_batch(
    body: LocationBatchRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """GPS batch — pings 를 location_ping 테이블에 bulk insert."""
    from location_ping.model import LocationPingModel
    if not body.pings:
        return None
    svc = DriverMobileService(db, team_id)
    driver_id = await svc.resolve_driver_id(int(me.id))
    for p in body.pings:
        db.add(LocationPingModel(
            team_id=team_id,
            driver_id=driver_id,
            latitude=p.latitude,
            longitude=p.longitude,
            speed_kmh=p.speed_kmh,
            heading_deg=p.heading_deg,
            accuracy_m=p.accuracy_m,
            occurred_at=p.occurred_at,
        ))
    await db.flush()
    await db.commit()
    return None


@router.post("/push-tokens", status_code=201)
async def upsert_push_token(
    body: PushTokenRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """FCM/APNs 토큰 upsert (driver+platform+token unique)."""
    from sqlalchemy import select
    from push_token.model import PushTokenModel

    svc = DriverMobileService(db, team_id)
    driver_id = await svc.resolve_driver_id(int(me.id))

    now = datetime.now(timezone.utc)
    existing = (await db.execute(
        select(PushTokenModel).where(
            PushTokenModel.team_id == team_id,
            PushTokenModel.driver_id == driver_id,
            PushTokenModel.platform == body.platform,
            PushTokenModel.token == body.token,
        )
    )).scalar_one_or_none()

    if existing:
        existing.last_used_at = now
        existing.is_active = True
        await db.flush()
        await db.commit()
        await db.refresh(existing)
        row = existing
    else:
        row = PushTokenModel(
            team_id=team_id,
            driver_id=driver_id,
            platform=body.platform,
            token=body.token,
            last_used_at=now,
        )
        db.add(row)
        await db.flush()
        await db.commit()
        await db.refresh(row)

    return {
        "id": row.id,
        "platform": row.platform,
        "token": row.token,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/legs/{leg_id}/documents", status_code=201)
async def upload_leg_document(
    leg_id: int,
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()],
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """POD/Receipt 등 leg 첨부 — multipart 1회. file.service 활용.

    검증:
    - content_type 화이트리스트 (image/* + pdf)
    - 본문 크기 ≤ 10MB
    - 본인 driver 의 leg 인지 검증
    """
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

    # 본인 leg 검증
    svc = DriverMobileService(db, team_id)
    driver_id = await svc.resolve_driver_id(int(me.id))
    from leg.model import LegModel
    leg = (await db.execute(
        select(LegModel).where(
            LegModel.team_id == team_id,
            LegModel.id == leg_id,
            LegModel.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if not leg:
        raise NotFoundException("Leg")
    if leg.driver_id != driver_id:
        raise HTTPException(status_code=403, detail={
            "code": "ERR_FORBIDDEN_LEG",
            "message": "Leg not assigned to current driver"})

    # FileService.direct_upload — multipart 본문 → S3 PUT + FileAsset 행 생성
    from file.service import FileService
    from file.const.domains import FileDomain
    file_svc = FileService(db)
    asset = await file_svc.direct_upload(
        team_id=team_id,
        domain=FileDomain.LEG_DOCUMENT,
        object_id=leg_id,
        file_bytes=body,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        actor_user_id=int(me.id),
        subdir=kind.lower() if kind else "",
    )
    await db.commit()

    return {
        "id": asset.id,
        "legId": leg_id,
        "kind": kind,
        "filename": asset.filename,
        "sizeBytes": asset.size,
        "mime": asset.mime,
        "logicalPath": asset.logical_path,
    }


@router.patch("/me/password")
async def change_first_password(
    body: FirstPasswordChangeRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    db: AsyncSession = Depends(get_write_db),
):
    """첫 로그인 비밀번호 강제 변경 — must_change_password 플래그 해제."""
    from user.model import UserModel
    from sqlalchemy import select

    # bcrypt 해시
    try:
        from passlib.hash import bcrypt
        password_hash = bcrypt.using(rounds=settings.BCRYPT_ROUNDS).hash(body.new_password)
    except Exception:
        # fallback (passlib 미설치 시)
        import bcrypt as _bcrypt
        password_hash = _bcrypt.hashpw(
            body.new_password.encode("utf-8"),
            _bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS),
        ).decode("utf-8")

    user = (await db.execute(
        select(UserModel).where(UserModel.id == int(me.id))
    )).scalar_one_or_none()
    if not user:
        raise NotFoundException("User")

    user.password = password_hash
    # must_change_password 플래그가 user 모델에 있다면 해제 (없을 수도)
    if hasattr(user, "must_change_password"):
        user.must_change_password = False
    await db.flush()
    await db.commit()
    return {"status": "ok"}
