# src/leg_layer/schemas/response.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from common.schemas.base import ResponseSchema
from leg_layer.const.status import LegAddonCode, LegChargeEventCode


class LegAddonResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    code: LegAddonCode
    amount_override: Decimal | None = None
    extra: dict | None = None
    note: str | None = None
    is_active: bool


class LegChargeEventResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    code: LegChargeEventCode
    enabled: bool
    free_minutes: int | None = None
    free_days: int | None = None
    actual_minutes: int | None = None
    actual_days: int | None = None
    note: str | None = None
    is_active: bool


class LegStopOffResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    seq: int
    location_id: int | None = None
    name: str | None = None
    arrived_at: datetime | None = None
    departed_at: datetime | None = None
    signed: bool
    pod_file_id: int | None = None
    note: str | None = None
    is_active: bool


class LegLayerDeleteResponseSchema(ResponseSchema):
    id: int
    deleted: bool = True
