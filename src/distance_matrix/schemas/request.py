# src/distance_matrix/schemas/request.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from leg.const.status import DistanceProvider


class DistanceMatrixCreateRequest(RequestSchema):
    origin_location_id: int
    destination_location_id: int
    distance_value: Decimal
    duration_min: Decimal = Decimal("0")
    source: DistanceProvider = DistanceProvider.MANUAL
    measured_at: datetime | None = None
    note: str | None = None


class DistanceMatrixUpdateRequest(RequestSchema):
    distance_value: Decimal | None = None
    duration_min: Decimal | None = None
    source: DistanceProvider | None = None
    measured_at: datetime | None = None
    note: str | None = None


class DistanceMatrixMeasureRequest(RequestSchema):
    """provider 어댑터로 거리 측정 요청. 결과는 distance_matrix row 로 캐시됨."""
    origin_location_id: int
    destination_location_id: int
    provider: DistanceProvider | None = None  # None 이면 team 설정 사용


class PaginateDistanceMatrixRequest(BasePaginationSchema):
    where__origin_location_id__equal: int | None = None
    where__destination_location_id__equal: int | None = None
    include_inactive: bool = False
