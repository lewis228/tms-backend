# src/container/schemas/response.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, List, Optional

from common.schemas.base import ResponseSchema
from container.const.status import (
    ContainerStatus, ContainerSize, ContainerEventKind,
)
from leg.const.status import (
    ServiceType, ContainerState, StopRole, MoveTypeV3,
    LegStatus, HandoverReason,
    LegLocationType, LegMoveCode,
)


class ContainerResponseSchema(ResponseSchema):
    id: int
    delivery_order_id: int
    sequence_no: int
    container_number: str | None = None
    seal_no: str | None = None
    size: ContainerSize | None = None
    type: str | None = None
    weight_kg: Decimal | None = None
    chassis_id: int | None = None
    pickup_appointment: datetime | None = None
    delivery_appointment: datetime | None = None
    return_appointment: datetime | None = None
    demurrage_lfd: date | None = None
    detention_lfd: date | None = None
    empty_date: datetime | None = None
    loaded_date: datetime | None = None
    delivery_location_id: int | None = None
    return_location_id: int | None = None
    service_type: ServiceType | None = None
    pier_pass_paid: bool
    customs_cleared: bool
    status: ContainerStatus
    work_state: ContainerState | None = None
    note: str | None = None
    is_active: bool

    # ── v3 list 행 enrich (Dispatch Workspace 컨테이너 단위 뷰용) ─────
    # service 의 list_paginated 가 채움. 미사용 시 None.
    bl_number:        str | None = None
    booking_number:   str | None = None
    customer_id:      int | None = None
    customer_name:    str | None = None
    direction:        str | None = None  # IMPORT / EXPORT
    move_type_v3:     MoveTypeV3 | None = None
    next_stop_id:     int | None = None
    current_driver_id:   int | None = None
    current_driver_name: str | None = None
    legs_total:       int | None = None
    legs_completed:   int | None = None


class ContainerDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["container"] = "container"
    deleted: bool = True
    soft_deleted: bool = False


# ── 이벤트 ─────────────────────────────────────────────

class ContainerEventResponseSchema(ResponseSchema):
    id: int
    container_id: int
    leg_id: int | None = None
    event_kind: ContainerEventKind
    location_id: int | None = None
    occurred_at: datetime
    note: str | None = None
    is_active: bool


# ── Bulk ──

class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class ContainerBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary


# ─── v3 Container 상세 (full) 응답 ──────────────────────────

class StopResponseSchema(ResponseSchema):
    id: int
    container_id: int
    sequence_no: int
    role: StopRole
    location_id: int | None = None
    location_name: str | None = None
    planned_arrival:   datetime | None = None
    planned_departure: datetime | None = None
    actual_arrival:    datetime | None = None
    actual_departure:  datetime | None = None
    note: str | None = None
    is_active: bool


class DriverSegmentResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    sequence_no: int
    driver_id: int
    driver_name: str | None = None
    truck_id: int | None = None
    started_at: datetime | None = None
    ended_at:   datetime | None = None
    handover_reason: HandoverReason | None = None
    note: str | None = None
    is_active: bool


class LegFullSchema(ResponseSchema):
    id: int
    delivery_order_id: int
    container_id: int | None = None
    from_stop_id: int | None = None
    to_stop_id:   int | None = None
    move_type_v3: MoveTypeV3 | None = None
    service_type: ServiceType | None = None
    from_location_type: LegLocationType | None = None
    to_location_type: LegLocationType | None = None
    move_code: LegMoveCode | None = None
    status: LegStatus
    driver_id: int | None = None
    driver_name: str | None = None
    started_at:   datetime | None = None
    arrived_at:   datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None
    reissued_from_leg_id: int | None = None
    note: str | None = None
    is_active: bool

    segments: List[DriverSegmentResponseSchema] = []


class ContainerFullResponseSchema(ResponseSchema):
    container: ContainerResponseSchema
    delivery_order: dict   # {id, bl_number, booking_number, reference, customer_id, customer_name, direction, eta, terminal_id, terminal_name, vessel_id, vessel_name, b_l_released}
    stops: List[StopResponseSchema] = []
    legs:  List[LegFullSchema] = []
    events: List[ContainerEventResponseSchema] = []
