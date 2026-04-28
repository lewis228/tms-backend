# src/leg_stop/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from leg.const.status import StopKind


class LegStopResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    sequence_no: int
    stop_kind: StopKind
    location_id: int | None = None
    container_id: int | None = None
    chassis_id: int | None = None
    arrived_at: datetime | None = None
    departed_at: datetime | None = None
    note: str | None = None
    is_active: bool


class LegStopDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["leg_stop"] = "leg_stop"
    deleted: bool = True
    soft_deleted: bool = False


class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class LegStopBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
