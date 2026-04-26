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
