"""Leg 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.schema import BaseSchema
from app.models.enums import DeliveryStatus, LegStatus, MoveType, ServiceType


class LegCreateRequest(BaseSchema):
    delivery_order_id: str
    step: DeliveryStatus
    move_type: MoveType
    service_type: ServiceType

    driver_id: str | None = None
    pickup_location_id: str | None = None
    pickup_date: datetime | None = None
    delivery_location_id: str | None = None
    delivery_date: datetime | None = None
    note: str | None = None


class LegUpdateRequest(BaseSchema):
    step: DeliveryStatus | None = None
    move_type: MoveType | None = None
    service_type: ServiceType | None = None
    driver_id: str | None = None
    pickup_location_id: str | None = None
    pickup_date: datetime | None = None
    delivery_location_id: str | None = None
    delivery_date: datetime | None = None
    note: str | None = None


class LegStatusTransitionRequest(BaseSchema):
    target: LegStatus
    failure_reason: str | None = Field(default=None, max_length=500)


class LegResponse(BaseSchema):
    id: str
    tenant_id: str
    delivery_order_id: str
    step: DeliveryStatus
    move_type: MoveType
    service_type: ServiceType
    status: LegStatus

    driver_id: str | None
    pickup_location_id: str | None
    pickup_date: datetime | None
    delivery_location_id: str | None
    delivery_date: datetime | None

    started_at: datetime | None
    arrived_at: datetime | None
    completed_at: datetime | None
    failure_reason: str | None

    storage_days: int
    is_settled: bool
    settlement_id: str | None
    note: str | None

    created_at: datetime
    updated_at: datetime
