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
