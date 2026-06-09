# src/leg_layer/schemas/request.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import Field

from common.schemas.base import RequestSchema
from leg_layer.const.status import LegAddonCode, LegChargeEventCode


# ── Layer 2: Add-on ─────────────────────────────────────────
class LegAddonCreateRequest(RequestSchema):
    leg_id: int
    code: LegAddonCode
    amount_override: Decimal | None = None
    extra: dict | None = None
    note: str | None = Field(default=None, max_length=300)


class LegAddonUpdateRequest(RequestSchema):
    amount_override: Decimal | None = None
    extra: dict | None = None
    note: str | None = Field(default=None, max_length=300)


# ── Layer 3: Charge Event (upsert by leg+code) ──────────────
class LegChargeEventUpsertRequest(RequestSchema):
    leg_id: int
    code: LegChargeEventCode
    enabled: bool = True
    free_minutes: int | None = None
    free_days: int | None = None
    actual_minutes: int | None = None
    actual_days: int | None = None
    note: str | None = Field(default=None, max_length=300)


# ── Stop Off ────────────────────────────────────────────────
class LegStopOffCreateRequest(RequestSchema):
    leg_id: int
    seq: int = Field(ge=1)
    location_id: int | None = None
    name: str | None = Field(default=None, max_length=200)
    arrived_at: datetime | None = None
    departed_at: datetime | None = None
    signed: bool = False
    pod_file_id: int | None = None
    note: str | None = Field(default=None, max_length=300)


class LegStopOffUpdateRequest(RequestSchema):
    seq: Optional[int] = Field(default=None, ge=1)
    location_id: int | None = None
    name: str | None = Field(default=None, max_length=200)
    arrived_at: datetime | None = None
    departed_at: datetime | None = None
    signed: bool | None = None
    pod_file_id: int | None = None
    note: str | None = Field(default=None, max_length=300)
