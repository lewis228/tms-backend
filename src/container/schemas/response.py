# src/container/schemas/response.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, List, Optional

from common.schemas.base import ResponseSchema
from container.const.status import (
    ContainerStatus, ContainerSize, ContainerEventKind,
)
from leg.const.status import ServiceType


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
    note: str | None = None
    is_active: bool


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
