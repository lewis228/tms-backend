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
    FirstPasswordChangeRequest, StopReportRequest,
    DutyToggleRequest, LegRejectRequest, ChatSendRequest, ChatMarkReadRequest,
)
from driver_mobile.schemas.response import (  # noqa: F401
    TodayTasksResponse, PushTokenResponse, DriverV3TodayResponse,
    DriverMeResponse, TodaySummaryResponse, LegOfferView, LegOfferListResponse,
    LegSummaryView, LegHistoryListResponse, WeeklyRevenuePoint,
    MonthlySettlementResponse, SettlementListItem, ChatMessageView,
    DutyToggleResponse, LegDetailResponse,
)
from chat.service import ChatService
from chat.schemas.request import PaginateChatMessageRequest, ChatMessageCreateRequest as _ChatCreate
from driver_mobile.service import DriverMobileService
from driver_mobile.service_v3 import (
    get_today_containers_for_driver, report_stop_arrive, report_stop_depart,
)
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


# ─── v3 Container/Stop 단위 모바일 API ───────────────────────────

@router.get("/v3/today", response_model=DriverV3TodayResponse)
async def v3_today(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """v3: 기사가 활성으로 배정된 컨테이너 + Stop 시퀀스."""
    return await get_today_containers_for_driver(db, team_id, int(me.id))


@router.post("/v3/stops/{stop_id}/arrive")
async def v3_stop_arrive(
    stop_id: int,
    body: StopReportRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """v3: stop 도착 보고 → actual_arrival 저장 + work_state derive."""
    return await report_stop_arrive(
        db, team_id, int(me.id), stop_id,
        occurred_at=body.occurred_at,
    )


@router.post("/v3/stops/{stop_id}/depart")
async def v3_stop_depart(
    stop_id: int,
    body: StopReportRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """v3: stop 출발 보고 → actual_departure 저장 + work_state derive."""
    return await report_stop_depart(
        db, team_id, int(me.id), stop_id,
        occurred_at=body.occurred_at,
    )


# ════════════════════════════════════════════════════════════════════
#  데모용 BFF 라우트 (홈 / 배차 / 정산 / 채팅)
# ════════════════════════════════════════════════════════════════════

@router.get("/me", response_model=DriverMeResponse)
async def get_me(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """본인 driver + user + 차량 정보 (홈 / 마이페이지)."""
    data = await DriverMobileService(db, team_id).get_me(int(me.id))
    return DriverMeResponse(**data)


@router.post("/duty-status", response_model=DutyToggleResponse)
async def toggle_duty(
    body: DutyToggleRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """근무 상태 토글 (OFF_DUTY / ON_DUTY / IN_BREAK)."""
    data = await DriverMobileService(db, team_id).toggle_duty(int(me.id), body.target)
    return DutyToggleResponse(**data)


@router.get("/today/summary", response_model=TodaySummaryResponse)
async def today_summary(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """오늘 요약 — 완료 수 + 예상 수익 + 거리 + on_duty 분."""
    data = await DriverMobileService(db, team_id).today_summary(int(me.id))
    return TodaySummaryResponse(**data)


@router.get("/legs/active", response_model=list[LegResponseSchema])
async def list_active_legs(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """진행 중 leg (IN_TRANSIT, accepted)."""
    legs = await DriverMobileService(db, team_id).list_active_legs(int(me.id))
    return [LegResponseSchema.model_validate(l) for l in legs]


@router.get("/legs/pending", response_model=LegOfferListResponse)
async def list_pending_offers(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """미수락 배차 (배차 알림 모달 polling)."""
    data = await DriverMobileService(db, team_id).list_pending_offers(int(me.id))
    return LegOfferListResponse(offers=[LegOfferView(**d) for d in data])


@router.post("/legs/{leg_id}/accept", response_model=LegResponseSchema)
async def accept_leg(
    leg_id: int,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """배차 수락 — accepted_at 기록."""
    leg = await DriverMobileService(db, team_id).accept_offer(leg_id, user_id=int(me.id))
    return LegResponseSchema.model_validate(leg)


@router.post("/legs/{leg_id}/reject", response_model=LegResponseSchema)
async def reject_leg(
    leg_id: int,
    body: LegRejectRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """배차 거절 + 사유 기록 + driver_id NULL 처리."""
    leg = await DriverMobileService(db, team_id).reject_offer(
        leg_id, user_id=int(me.id), reason=body.reason,
    )
    return LegResponseSchema.model_validate(leg)


@router.get("/legs/history", response_model=LegHistoryListResponse)
async def list_history(
    before_id: int | None = None,
    limit: int = 20,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """운행 이력 페이지네이션 (COMPLETED 만)."""
    data = await DriverMobileService(db, team_id).list_history(
        int(me.id), before_id=before_id, limit=min(limit, 100),
    )
    return LegHistoryListResponse(
        items=[LegSummaryView(**d) for d in data["items"]],
        has_more=data["has_more"],
        next_cursor=data["next_cursor"],
    )


@router.get("/settlement/monthly", response_model=MonthlySettlementResponse)
async def settlement_monthly(
    year: int | None = None,
    month: int | None = None,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """정산 월간 통계 (총액 + 주간추이 + 상태별 카운트)."""
    data = await DriverMobileService(db, team_id).monthly_settlement_summary(
        int(me.id), year=year, month=month,
    )
    return MonthlySettlementResponse(
        year=data["year"], month=data["month"],
        total_amount=data["total_amount"],
        completed_count=data["completed_count"],
        pending_count=data["pending_count"],
        on_hold_count=data["on_hold_count"],
        weekly_trend=[WeeklyRevenuePoint(**w) for w in data["weekly_trend"]],
    )


@router.get("/settlement/list")
async def settlement_list(
    before_id: int | None = None,
    limit: int = 20,
    status: str | None = None,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """정산 목록 (페이지네이션, 상태 필터)."""
    data = await DriverMobileService(db, team_id).list_settlements(
        int(me.id), before_id=before_id, limit=min(limit, 100), status_filter=status,
    )
    # camelCase 응답 (ResponseSchema 정책과 일치 — Flutter/Web 클라이언트 호환)
    return {
        "items": [SettlementListItem(**d).model_dump(by_alias=True) for d in data["items"]],
        "hasMore": data["has_more"],
        "nextCursor": data["next_cursor"],
    }


# ── 채팅 ─────────────────────────────────────────────────────

@router.get("/chat/messages")
async def chat_list_messages(
    take: int = 30,
    where__id__less_than: int | None = None,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """본인 conversation 메시지 페이지네이션 (DESC = 최신부터)."""
    req = PaginateChatMessageRequest(
        take=take, where__id__less_than=where__id__less_than,
    )
    result = await ChatService(db, team_id).list_paginated_for_driver(req, int(me.id))
    return result


@router.post("/chat/messages")
async def chat_send_message(
    body: ChatSendRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """driver → 관제. 데모용 자동 응답 1.5초 후 자동 생성."""
    create = _ChatCreate(content=body.content)
    return await ChatService(db, team_id).send_from_driver(create, driver_user_id=int(me.id))


@router.post("/chat/messages/read", status_code=204)
async def chat_mark_read(
    body: ChatMarkReadRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """수신 메시지 읽음 처리."""
    await ChatService(db, team_id).mark_read(int(me.id), before_id=body.before_id)
    return None


@router.get("/chat/unread-count")
async def chat_unread_count(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """배지 카운트용 — 읽지 않은 dispatcher/system 메시지 수."""
    count = await ChatService(db, team_id).unread_count_for_driver(int(me.id))
    return {"unread_count": count}


# ── 오더 상세 (화면 4) ───────────────────────────

@router.get("/legs/{leg_id}", response_model=LegDetailResponse)
async def get_leg_detail(
    leg_id: int,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """오더 상세 — leg + delivery_order + customer + locations + container 한 응답."""
    data = await DriverMobileService(db, team_id).get_leg_detail(
        leg_id, user_id=int(me.id),
    )
    return LegDetailResponse(**data)
