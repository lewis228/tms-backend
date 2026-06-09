# src/leg/schemas/response.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from delivery_order.const.status import DeliveryStatus
from leg.const.status import (
    LegStatus, MoveType, ServiceType, LegKind, LegLocationType, LegMoveCode,
)


class LegResponseSchema(ResponseSchema):
    id: int
    delivery_order_id: int
    container_id: int | None = None
    truck_id: int | None = None
    chassis_id: int | None = None
    chassis_at_start_id: int | None = None
    chassis_at_end_id: int | None = None
    container_at_start_id: int | None = None
    container_at_end_id: int | None = None
    step: DeliveryStatus
    move_type: MoveType
    service_type: ServiceType
    leg_kind: LegKind | None = None
    from_location_type: LegLocationType | None = None
    to_location_type: LegLocationType | None = None
    move_code: LegMoveCode | None = None
    rate_point_id: int | None = None
    dest_zip: str | None = None
    dest_city: str | None = None
    dest_state: str | None = None
    rate_miles: Decimal | None = None
    rate_hours: Decimal | None = None
    status: LegStatus
    driver_id: int | None = None
    assigned_at: datetime | None = None
    offered_at: datetime | None = None
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    pickup_location_id: int | None = None
    pickup_date: datetime | None = None
    delivery_location_id: int | None = None
    delivery_date: datetime | None = None
    started_at: datetime | None = None
    arrived_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None
    reissued_from_leg_id: int | None = None
    storage_days: int
    is_settled: bool
    remarks: str | None = None
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
