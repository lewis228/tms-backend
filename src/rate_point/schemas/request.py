# src/rate_point/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from rate_point.const.status import PointType


class RatePointCreateRequest(RequestSchema):
    """Rate Point 생성 DTO."""
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    point_type: PointType
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    terminal_id: int | None = None
    location_id: int | None = None
    note: str | None = Field(default=None, max_length=3000)


class RatePointUpdateRequest(RequestSchema):
    """Rate Point 수정 DTO (부분 수정 허용)."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    point_type: PointType | None = None
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    terminal_id: int | None = None
    location_id: int | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateRatePointRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'

    include_inactive: bool = False

    where__name__i_like: Optional[str] = None
    where__code__i_like: Optional[str] = None
    where__point_type__equal: Optional[PointType] = None


class RatePointBulkCreateRequest(RequestSchema):
    items: List[RatePointCreateRequest] = Field(..., min_length=1, max_length=100)


class RatePointBulkUpdateItem(RequestSchema):
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    point_type: PointType | None = None
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    terminal_id: int | None = None
    location_id: int | None = None
    note: str | None = Field(default=None, max_length=3000)


class RatePointBulkUpdateRequest(RequestSchema):
    items: List[RatePointBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class RatePointBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
