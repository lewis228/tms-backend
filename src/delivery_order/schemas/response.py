# src/delivery_order/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from delivery_order.const.status import (
    DeliveryStatus, ShipmentDirection,
)
from container.schemas.response import ContainerResponseSchema


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
    internal_note: str | None = None
    is_active: bool


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
