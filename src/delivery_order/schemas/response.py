# src/delivery_order/schemas/response.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from delivery_order.const.status import (
    DeliveryStatus, ShipmentDirection,
)
from container.schemas.response import ContainerResponseSchema


class EtaStatus(StrEnum):
    OVERDUE = "OVERDUE"
    URGENT = "URGENT"
    OK = "OK"
    NONE = "NONE"


class DeliveryOrderResponseSchema(ResponseSchema):
    id: int
    status: DeliveryStatus
    direction: ShipmentDirection
    bl_number: str | None = None
    booking_number: str | None = None
    reference: str | None = None
    customer_id: int
    terminal_id: int | None = None
    vessel_id: int | None = None
    eta: datetime | None = None
    bl_released: bool
    is_on_hold: bool = False
    hold_reason: str | None = None
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    internal_note: str | None = None
    is_active: bool

    # H-10: list 응답에만 채워지는 파생 필드 (단건 조회는 None)
    container_count: int | None = None
    container_completed_count: int | None = None
    margin_preview: Decimal | None = None
    eta_status: EtaStatus | None = None


class DeliveryOrderDetailResponseSchema(DeliveryOrderResponseSchema):
    """D/O 단건 조회 — 컨테이너 nested 포함."""
    containers: List[ContainerResponseSchema] = []


class DeliveryOrderDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["delivery_order"] = "delivery_order"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[DeliveryOrderResponseSchema] = None
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


class DeliveryOrderBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class DeliveryOrderBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class DeliveryOrderBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
