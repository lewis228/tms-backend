# src/driver_mobile/schemas/request.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pydantic import Field
from common.schemas.base import RequestSchema
from leg.const.status import LegStatus


class CheckpointRequest(RequestSchema):
    target: LegStatus
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)
    failure_reason: str | None = Field(default=None, max_length=500)


class LocationPing(RequestSchema):
    latitude: Decimal
    longitude: Decimal
    speed_kmh: Decimal | None = None
    heading_deg: Decimal | None = None
    accuracy_m: Decimal | None = None
    occurred_at: datetime


class LocationBatchRequest(RequestSchema):
    pings: list[LocationPing] = Field(default_factory=list)


class PushTokenRequest(RequestSchema):
    platform: str = Field(..., max_length=16)
    token: str = Field(..., max_length=512)


class FirstPasswordChangeRequest(RequestSchema):
    new_password: str = Field(..., min_length=8, max_length=128)


# ─── v3 Stop arrive/depart ─────────────────────────────────────
class StopReportRequest(RequestSchema):
    """기사가 모바일에서 stop 도착/출발 보고."""
    occurred_at: datetime | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    note: str | None = Field(default=None, max_length=500)


# ══════════════════════════════════════════════════════════════════
# 신규: 데모용 BFF 라우트 (홈 / 배차 / 정산 / 채팅)
# ══════════════════════════════════════════════════════════════════

class DutyToggleRequest(RequestSchema):
    """근무 상태 토글."""
    target: str = Field(..., description="OFF_DUTY / ON_DUTY / IN_BREAK")


class LegRejectRequest(RequestSchema):
    """배차 거절 사유."""
    reason: str = Field(..., max_length=500)


class ChatSendRequest(RequestSchema):
    """채팅 메시지 전송."""
    content: str = Field(..., min_length=1, max_length=2000)


class ChatMarkReadRequest(RequestSchema):
    """채팅 읽음 처리."""
    before_id: int | None = Field(
        None, description="None 이면 전체. id 명시 시 그 id 이하만 읽음 처리.",
    )
