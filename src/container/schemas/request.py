# src/container/schemas/request.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Literal, List

from pydantic import Field, field_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from container.const.status import (
    ContainerStatus, ContainerSize, ContainerEventKind,
)
from leg.const.status import ServiceType


CONTAINER_NUMBER_PATTERN = r"^[A-Z]{4}\d{7}$"


class StopCreateInner(RequestSchema):
    """v3: D/O Create 시 컨테이너에 nested 로 받는 stop 1건.

    AI Intake 추출 또는 수동 입력. location_id 가 None 이면 location_name 으로
    fuzzy 매칭 시도 (DOService 가 처리). 매칭 실패 시 location_id null 로 stop 생성.
    """
    role: str  # ORIGIN / DELIVERY / TRANSIT / TERMINUS
    sequence_no: int | None = None
    location_id: int | None = None
    location_name: str | None = None  # fuzzy 매칭용
    planned_arrival: datetime | None = None
    planned_departure: datetime | None = None
    note: str | None = Field(default=None, max_length=500)


class ContainerCreateInner(RequestSchema):
    """D/O Create 시 nested 로 받는 컨테이너 1건. (delivery_order_id 는 D/O 생성 시 부착)"""
    sequence_no: int | None = None
    container_number: str | None = Field(default=None, pattern=CONTAINER_NUMBER_PATTERN)
    seal_no: str | None = Field(default=None, max_length=64)
    size: ContainerSize | None = None
    type: str | None = Field(default=None, max_length=32)
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
    pier_pass_paid: bool = False
    customs_cleared: bool = False
    status: ContainerStatus = ContainerStatus.PLANNING
    note: str | None = Field(default=None, max_length=3000)
    # v3: AI Intake 가 추출한 stop 시퀀스. 비어있으면 stop 생성 X (수동 추가 가능).
    stops: List["StopCreateInner"] = Field(default_factory=list)


class ContainerCreateRequest(ContainerCreateInner):
    """단독 컨테이너 추가 (D/O 1건에 컨 N개 추가 시)."""
    delivery_order_id: int


class ContainerUpdateRequest(RequestSchema):
    """부분 수정."""
    sequence_no: int | None = None
    container_number: str | None = Field(default=None, pattern=CONTAINER_NUMBER_PATTERN)
    seal_no: str | None = Field(default=None, max_length=64)
    size: ContainerSize | None = None
    type: str | None = Field(default=None, max_length=32)
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
    pier_pass_paid: bool | None = None
    customs_cleared: bool | None = None
    status: ContainerStatus | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateContainerRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__delivery_order_id__equal: Optional[int] = None
    where__container_number__i_like: Optional[str] = None
    where__status__equal: Optional[ContainerStatus] = None


# ── 이벤트 ────────────────────────────────────────────────────────

class ContainerEventCreateRequest(RequestSchema):
    event_kind: ContainerEventKind
    location_id: int | None = None
    leg_id: int | None = None
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=3000)


class PaginateContainerEventRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__container_id__equal: Optional[int] = None
    where__event_kind__equal: Optional[ContainerEventKind] = None


# ── Bulk ─────────────────────────────────────────────────────────

class ContainerBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
