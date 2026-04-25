"""DeliveryOrder 스키마."""
from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import Field, field_validator

from app.core.schema import BaseSchema
from app.models.enums import ContainerSize, DeliveryStatus, ShipmentDirection

_CONTAINER_RE = re.compile(r"^[A-Z]{4}\d{7}$")


class DeliveryOrderCreateRequest(BaseSchema):
    direction: ShipmentDirection
    customer_id: str

    bl_number: str | None = Field(default=None, max_length=64)
    booking_number: str | None = Field(default=None, max_length=64)
    reference: str | None = Field(default=None, max_length=128)

    container_number: str | None = None
    container_size: ContainerSize | None = None
    container_type: str | None = Field(default=None, max_length=32)
    chassis_number: str | None = Field(default=None, max_length=32)

    terminal_id: str | None = None
    vessel_id: str | None = None
    delivery_location_id: str | None = None
    return_location_id: str | None = None

    eta: datetime | None = None
    pickup_appointment: datetime | None = None
    delivery_appointment: datetime | None = None
    return_appointment: datetime | None = None
    demurrage_lfd: date | None = None
    detention_lfd: date | None = None
    empty_date: date | None = None
    loaded_date: date | None = None

    bl_released: bool = False
    pier_pass_paid: bool = False
    customs_cleared: bool = False

    internal_note: str | None = None

    @field_validator("container_number")
    @classmethod
    def _validate_container(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.upper().replace(" ", "").replace("-", "")
        if not _CONTAINER_RE.match(v):
            raise ValueError("container_number must match ^[A-Z]{4}\\d{7}$")
        return v


class DeliveryOrderUpdateRequest(BaseSchema):
    bl_number: str | None = Field(default=None, max_length=64)
    booking_number: str | None = Field(default=None, max_length=64)
    reference: str | None = Field(default=None, max_length=128)

    container_number: str | None = None
    container_size: ContainerSize | None = None
    container_type: str | None = Field(default=None, max_length=32)
    chassis_number: str | None = Field(default=None, max_length=32)

    terminal_id: str | None = None
    vessel_id: str | None = None
    delivery_location_id: str | None = None
    return_location_id: str | None = None

    eta: datetime | None = None
    pickup_appointment: datetime | None = None
    delivery_appointment: datetime | None = None
    return_appointment: datetime | None = None
    demurrage_lfd: date | None = None
    detention_lfd: date | None = None
    empty_date: date | None = None
    loaded_date: date | None = None

    bl_released: bool | None = None
    pier_pass_paid: bool | None = None
    customs_cleared: bool | None = None

    internal_note: str | None = None

    @field_validator("container_number")
    @classmethod
    def _validate_container(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.upper().replace(" ", "").replace("-", "")
        if not _CONTAINER_RE.match(v):
            raise ValueError("container_number must match ^[A-Z]{4}\\d{7}$")
        return v


class StatusTransitionRequest(BaseSchema):
    target: DeliveryStatus


class DeliveryOrderResponse(BaseSchema):
    id: str
    tenant_id: str
    status: DeliveryStatus
    direction: ShipmentDirection
    bl_number: str | None
    booking_number: str | None
    reference: str | None
    customer_id: str
    terminal_id: str | None
    vessel_id: str | None
    delivery_location_id: str | None
    return_location_id: str | None
    container_number: str | None
    container_size: ContainerSize | None
    container_type: str | None
    chassis_number: str | None
    eta: datetime | None
    pickup_appointment: datetime | None
    delivery_appointment: datetime | None
    return_appointment: datetime | None
    demurrage_lfd: date | None
    detention_lfd: date | None
    empty_date: date | None
    loaded_date: date | None
    bl_released: bool
    pier_pass_paid: bool
    customs_cleared: bool
    internal_note: str | None
    created_at: datetime
    updated_at: datetime
