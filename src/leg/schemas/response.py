# src/leg/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from delivery_order.const.status import DeliveryStatus
from leg.const.status import LegStatus, MoveType, ServiceType


class LegResponseSchema(ResponseSchema):
    id: int
    delivery_order_id: int
    step: DeliveryStatus
    move_type: MoveType
    service_type: ServiceType
    status: LegStatus
    driver_id: int | None = None
    pickup_location_id: int | None = None
    pickup_date: datetime | None = None
    delivery_location_id: int | None = None
    delivery_date: datetime | None = None
    started_at: datetime | None = None
    arrived_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None
    storage_days: int
    is_settled: bool
    note: str | None = None
    is_active: bool


class LegDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["leg"] = "leg"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[LegResponseSchema] = None
    error: Optional[str] = None


class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class LegBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class LegBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class LegBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
