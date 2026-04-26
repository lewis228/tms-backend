# src/delivery_order/schemas/response.py
from __future__ import annotations
from datetime import date, datetime
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from delivery_order.const.status import (
    DeliveryStatus, ShipmentDirection, ContainerSize,
)


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
    delivery_location_id: int | None = None
    return_location_id: int | None = None
    container_number: str | None = None
    container_size: ContainerSize | None = None
    container_type: str | None = None
    chassis_number: str | None = None
    eta: datetime | None = None
    pickup_appointment: datetime | None = None
    delivery_appointment: datetime | None = None
    return_appointment: datetime | None = None
    demurrage_lfd: date | None = None
    detention_lfd: date | None = None
    empty_date: datetime | None = None
    loaded_date: datetime | None = None
    bl_released: bool
    pier_pass_paid: bool
    customs_cleared: bool
    internal_note: str | None = None
    is_active: bool


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
