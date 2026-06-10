# src/chassis_event/schemas/response.py
from __future__ import annotations
from datetime import datetime
from common.schemas.base import ResponseSchema
from leg.const.status import ChassisEventKind


class ChassisEventResponseSchema(ResponseSchema):
    id: int
    chassis_id: int
    leg_id: int | None = None
    event_kind: ChassisEventKind
    location_id: int | None = None
    occurred_at: datetime
    note: str | None = None
    is_active: bool
