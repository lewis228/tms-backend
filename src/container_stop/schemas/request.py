# src/container_stop/schemas/request.py
from __future__ import annotations
from datetime import datetime

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from leg.const.status import PointType


class ContainerStopCreateRequest(RequestSchema):
    container_id: int
    point_type: PointType
    # 타입별 마스터 참조 (point_type 에 맞는 하나만 채움 — 서비스에서 검증)
    terminal_id: int | None = None
    location_id: int | None = None
    customer_id: int | None = None
    sequence_no: int | None = None  # 미지정 시 자동 다음 번호
    planned_arrival:   datetime | None = None
    planned_departure: datetime | None = None
    actual_arrival:    datetime | None = None
    actual_departure:  datetime | None = None
    note: str | None = None


class ContainerStopUpdateRequest(RequestSchema):
    point_type: PointType | None = None
    terminal_id: int | None = None
    location_id: int | None = None
    customer_id: int | None = None
    sequence_no: int | None = None
    planned_arrival:   datetime | None = None
    planned_departure: datetime | None = None
    actual_arrival:    datetime | None = None
    actual_departure:  datetime | None = None
    note: str | None = None


class PaginateContainerStopRequest(BasePaginationSchema):
    where__container_id__equal: int | None = None
    where__point_type__equal: PointType | None = None
    include_inactive: bool = False


class StopReorderItem(RequestSchema):
    stop_id: int
    sequence_no: int


class ContainerStopReorderRequest(RequestSchema):
    items: list[StopReorderItem]
