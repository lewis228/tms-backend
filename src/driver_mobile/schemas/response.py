# src/driver_mobile/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import List
from common.schemas.base import ResponseSchema
from leg.schemas.response import LegResponseSchema


class TodayTasksResponse(ResponseSchema):
    legs: List[LegResponseSchema]


class PushTokenResponse(ResponseSchema):
    id: int
    platform: str
    token: str
    last_used_at: datetime | None = None
    created_at: datetime


# ─── v3 Driver mobile — 컨테이너/Stop 단위 ──────────────────────

class DriverStopView(ResponseSchema):
    """기사가 보는 stop 카드."""
    id: int
    container_id: int
    sequence_no: int
    role: str  # ORIGIN / DELIVERY / TRANSIT / TERMINUS
    location_id: int | None = None
    location_name: str | None = None
    location_address: str | None = None
    planned_arrival: datetime | None = None
    actual_arrival: datetime | None = None
    actual_departure: datetime | None = None


class DriverContainerView(ResponseSchema):
    """기사 모바일의 컨테이너 카드."""
    container_id: int
    container_number: str | None = None
    size: str | None = None
    bl_number: str | None = None
    customer_name: str | None = None
    direction: str | None = None
    work_state: str | None = None
    legs_total: int = 0
    legs_completed: int = 0
    next_stop: DriverStopView | None = None  # 다음 미도착 stop
    stops: list[DriverStopView] = []


class DriverV3TodayResponse(ResponseSchema):
    containers: list[DriverContainerView] = []
