"""Driver 모바일 스키마."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.core.schema import BaseSchema
from app.domains.legs.schema import LegResponse
from app.models.enums import LegStatus


class CheckpointRequest(BaseSchema):
    target: LegStatus
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)
    failure_reason: str | None = Field(default=None, max_length=500)


class LocationPingRequest(BaseSchema):
    latitude: Decimal
    longitude: Decimal
    speed_kmh: Decimal | None = None
    heading_deg: Decimal | None = None
    accuracy_m: Decimal | None = None
    occurred_at: datetime


class LocationBatchRequest(BaseSchema):
    pings: list[LocationPingRequest]


class PushTokenRequest(BaseSchema):
    platform: str = Field(..., max_length=16)
    token: str = Field(..., max_length=512)


class PushTokenResponse(BaseSchema):
    id: str
    platform: str
    token: str
    last_used_at: datetime | None
    created_at: datetime


class TodayTasksResponse(BaseSchema):
    legs: list[LegResponse]


class FirstPasswordChangeRequest(BaseSchema):
    new_password: str = Field(..., min_length=8, max_length=128)
