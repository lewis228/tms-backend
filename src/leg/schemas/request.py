# src/leg/schemas/request.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from delivery_order.const.status import DeliveryStatus
from leg.const.status import (
    LegStatus, MoveType, ServiceType, PointType, LegMoveCode,
)


class LegCreateRequest(RequestSchema):
    delivery_order_id: int
    container_id: int | None = None
    step: DeliveryStatus
    move_type: MoveType
    service_type: ServiceType
    # 포인트 모델: from/to_point 선택 → 서비스가 point_type 을 from/to_location_type 으로 스냅샷.
    # 포인트 없이 타입만 직접 줄 수도 있음(Bobtail 등). move_code 는 Layer1 코드.
    from_point_id: int | None = None
    to_point_id: int | None = None
    from_location_type: PointType | None = None
    to_location_type: PointType | None = None
    move_code: LegMoveCode | None = None
    # 도착지 정산 입력 — 미지정 시 to_point 마스터의 zip_id 에서 자동 스냅샷(override 가능).
    dest_zip: str | None = Field(default=None, max_length=16)
    dest_city: str | None = Field(default=None, max_length=120)
    dest_state: str | None = Field(default=None, max_length=8)
    driver_id: int | None = None
    truck_id: int | None = None
    chassis_id: int | None = None
    chassis_at_start_id: int | None = None
    chassis_at_end_id: int | None = None
    container_at_start_id: int | None = None
    container_at_end_id: int | None = None
    remarks: str | None = Field(default=None, max_length=500)
    pickup_date: datetime | None = None
    delivery_date: datetime | None = None
    note: str | None = Field(default=None, max_length=3000)


class LegUpdateRequest(RequestSchema):
    container_id: int | None = None
    step: DeliveryStatus | None = None
    move_type: MoveType | None = None
    service_type: ServiceType | None = None
    from_point_id: int | None = None
    to_point_id: int | None = None
    from_location_type: PointType | None = None
    to_location_type: PointType | None = None
    move_code: LegMoveCode | None = None
    rate_point_id: int | None = None
    dest_zip: str | None = Field(default=None, max_length=16)
    dest_city: str | None = Field(default=None, max_length=120)
    dest_state: str | None = Field(default=None, max_length=8)
    rate_miles: Decimal | None = None
    rate_hours: Decimal | None = None
    driver_id: int | None = None
    truck_id: int | None = None
    chassis_id: int | None = None
    chassis_at_start_id: int | None = None
    chassis_at_end_id: int | None = None
    container_at_start_id: int | None = None
    container_at_end_id: int | None = None
    remarks: str | None = Field(default=None, max_length=500)
    pickup_date: datetime | None = None
    delivery_date: datetime | None = None
    note: str | None = Field(default=None, max_length=3000)


class LegTransitionRequest(RequestSchema):
    """Leg 상태 전이. FAILED 의 경우 failure_reason 필수."""
    target: LegStatus
    failure_reason: str | None = Field(default=None, max_length=500)


class LegAssignRequest(RequestSchema):
    """드라이버 배차 — PENDING leg 를 ASSIGNED 로."""
    driver_id: int
    truck_id: int | None = None
    chassis_id: int | None = None


class LegApplyLoadTypeRequest(RequestSchema):
    """Load Type 템플릿 → container leg 자동 생성."""
    container_id: int
    template_id: int
    replace_existing: bool = False


class LegReissueRequest(RequestSchema):
    """Dry Run 재발급 — 빠꾸 사유."""
    reason: str | None = None


class PaginateLegRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__delivery_order_id__equal: Optional[int] = None
    where__container_id__equal: Optional[int] = None
    where__driver_id__equal: Optional[int] = None
    where__truck_id__equal: Optional[int] = None
    where__status__equal: Optional[LegStatus] = None
    where__step__equal: Optional[DeliveryStatus] = None


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
