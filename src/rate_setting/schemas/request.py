# src/rate_setting/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from rate_setting.const.rate_type import RateType


class RateSettingCreateRequest(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    rate_type: RateType
    flat_amount: Decimal | None = None
    rate_percent: Decimal | None = None
    rate_per_mile: Decimal | None = None
    effective_date: date
    description: str | None = Field(default=None, max_length=3000)


class RateSettingUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    flat_amount: Decimal | None = None
    rate_percent: Decimal | None = None
    rate_per_mile: Decimal | None = None
    effective_date: date | None = None
    description: str | None = Field(default=None, max_length=3000)


class PaginateRateSettingRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__name__i_like: Optional[str] = None
    where__rate_type__equal: Optional[RateType] = None


class RateSettingBulkCreateRequest(RequestSchema):
    items: List[RateSettingCreateRequest] = Field(..., min_length=1, max_length=100)


class RateSettingBulkUpdateItem(RequestSchema):
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    flat_amount: Decimal | None = None
    rate_percent: Decimal | None = None
    rate_per_mile: Decimal | None = None
    effective_date: date | None = None
    description: str | None = Field(default=None, max_length=3000)


class RateSettingBulkUpdateRequest(RequestSchema):
    items: List[RateSettingBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class RateSettingBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
