# src/delivery_order/schemas/request.py
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from delivery_order.const.status import (
    DeliveryStatus, ShipmentDirection, ContainerSize,
)


CONTAINER_NUMBER_PATTERN = r"^[A-Z]{4}\d{7}$"


class DeliveryOrderCreateRequest(RequestSchema):
    direction: ShipmentDirection
    customer_id: int
    bl_number: str | None = Field(default=None, max_length=64)
    booking_number: str | None = Field(default=None, max_length=64)
    reference: str | None = Field(default=None, max_length=120)
    terminal_id: int | None = None
    vessel_id: int | None = None
    delivery_location_id: int | None = None
    return_location_id: int | None = None
    container_number: str | None = Field(default=None, pattern=CONTAINER_NUMBER_PATTERN)
    container_size: ContainerSize | None = None
    container_type: str | None = Field(default=None, max_length=32)
    chassis_number: str | None = Field(default=None, max_length=32)
    eta: datetime | None = None
    pickup_appointment: datetime | None = None
    delivery_appointment: datetime | None = None
    return_appointment: datetime | None = None
    demurrage_lfd: date | None = None
    detention_lfd: date | None = None
    empty_date: datetime | None = None
    loaded_date: datetime | None = None
    bl_released: bool = False
    pier_pass_paid: bool = False
    customs_cleared: bool = False
    internal_note: str | None = Field(default=None, max_length=3000)


class DeliveryOrderUpdateRequest(RequestSchema):
    bl_number: str | None = Field(default=None, max_length=64)
    booking_number: str | None = Field(default=None, max_length=64)
    reference: str | None = Field(default=None, max_length=120)
    terminal_id: int | None = None
    vessel_id: int | None = None
    delivery_location_id: int | None = None
    return_location_id: int | None = None
    container_number: str | None = Field(default=None, pattern=CONTAINER_NUMBER_PATTERN)
    container_size: ContainerSize | None = None
    container_type: str | None = Field(default=None, max_length=32)
    chassis_number: str | None = Field(default=None, max_length=32)
    eta: datetime | None = None
    pickup_appointment: datetime | None = None
    delivery_appointment: datetime | None = None
    return_appointment: datetime | None = None
    demurrage_lfd: date | None = None
    detention_lfd: date | None = None
    empty_date: datetime | None = None
    loaded_date: datetime | None = None
    bl_released: bool | None = None
    pier_pass_paid: bool | None = None
    customs_cleared: bool | None = None
    internal_note: str | None = Field(default=None, max_length=3000)


class DeliveryOrderTransitionRequest(RequestSchema):
    """D/O 상태 전이 — service 가 게이트 검증."""
    target: DeliveryStatus


class PaginateDeliveryOrderRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__status__equal: Optional[DeliveryStatus] = None
    where__direction__equal: Optional[ShipmentDirection] = None
    where__customer_id__equal: Optional[int] = None
    where__container_number__i_like: Optional[str] = None
    where__bl_number__i_like: Optional[str] = None


class DeliveryOrderBulkCreateRequest(RequestSchema):
    items: List[DeliveryOrderCreateRequest] = Field(..., min_length=1, max_length=100)


class DeliveryOrderBulkUpdateItem(DeliveryOrderUpdateRequest):
    id: int


class DeliveryOrderBulkUpdateRequest(RequestSchema):
    items: List[DeliveryOrderBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class DeliveryOrderBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
