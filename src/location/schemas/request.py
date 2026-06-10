# src/location/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from location.const.kind import LocationKind


class LocationCreateRequest(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    kind: LocationKind = LocationKind.YARD
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    customer_id: int | None = None
    zip_id: int | None = None       # 전역 zip 마스터 참조(정산 dest 자동채움)
    note: str | None = Field(default=None, max_length=3000)


class LocationUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: LocationKind | None = None
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    customer_id: int | None = None
    zip_id: int | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateLocationRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__name__i_like: Optional[str] = None
    where__kind__equal: Optional[LocationKind] = None
    where__customer_id__equal: Optional[int] = None


class LocationBulkCreateRequest(RequestSchema):
    items: List[LocationCreateRequest] = Field(..., min_length=1, max_length=100)


class LocationBulkUpdateItem(RequestSchema):
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: LocationKind | None = None
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    customer_id: int | None = None
    note: str | None = Field(default=None, max_length=3000)


class LocationBulkUpdateRequest(RequestSchema):
    items: List[LocationBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class LocationBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
