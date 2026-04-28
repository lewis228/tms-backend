# src/leg/schemas/request.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from delivery_order.const.status import DeliveryStatus
from leg.const.status import LegStatus, MoveType, ServiceType, LegKind


class LegCreateRequest(RequestSchema):
    delivery_order_id: int
    container_id: int | None = None
    step: DeliveryStatus
    move_type: MoveType
    service_type: ServiceType
    leg_kind: LegKind | None = None
    driver_id: int | None = None
    truck_id: int | None = None
    chassis_id: int | None = None
    chassis_at_start_id: int | None = None
    chassis_at_end_id: int | None = None
    container_at_start_id: int | None = None
    container_at_end_id: int | None = None
    remarks: str | None = Field(default=None, max_length=500)
    pickup_location_id: int | None = None
    pickup_date: datetime | None = None
    delivery_location_id: int | None = None
    delivery_date: datetime | None = None
    note: str | None = Field(default=None, max_length=3000)


class LegUpdateRequest(RequestSchema):
    container_id: int | None = None
    step: DeliveryStatus | None = None
    move_type: MoveType | None = None
    service_type: ServiceType | None = None
    leg_kind: LegKind | None = None
    driver_id: int | None = None
    truck_id: int | None = None
    chassis_id: int | None = None
    chassis_at_start_id: int | None = None
    chassis_at_end_id: int | None = None
    container_at_start_id: int | None = None
    container_at_end_id: int | None = None
    remarks: str | None = Field(default=None, max_length=500)
    pickup_location_id: int | None = None
    pickup_date: datetime | None = None
    delivery_location_id: int | None = None
    delivery_date: datetime | None = None
    note: str | None = Field(default=None, max_length=3000)


class LegTransitionRequest(RequestSchema):
    """Leg 상태 전이. FAILED 의 경우 failure_reason 필수."""
    target: LegStatus
    failure_reason: str | None = Field(default=None, max_length=500)


class PaginateLegRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__delivery_order_id__equal: Optional[int] = None
    where__container_id__equal: Optional[int] = None
    where__driver_id__equal: Optional[int] = None
    where__truck_id__equal: Optional[int] = None
    where__status__equal: Optional[LegStatus] = None
    where__step__equal: Optional[DeliveryStatus] = None
    where__leg_kind__equal: Optional[LegKind] = None


class LegBulkCreateRequest(RequestSchema):
    items: List[LegCreateRequest] = Field(..., min_length=1, max_length=100)


class LegBulkUpdateItem(LegUpdateRequest):
    id: int


class LegBulkUpdateRequest(RequestSchema):
    items: List[LegBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class LegBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
