# src/accessorial/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal
from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from accessorial.const.status import AccessorialCategory, AccessorialUnit


class AccessorialCreateRequest(RequestSchema):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=120)
    category: AccessorialCategory
    unit: AccessorialUnit
    amount: Decimal | None = None
    percent: Decimal | None = None
    free_minutes: int | None = None
    free_days: int | None = None
    auto_apply: bool = False
    driver_id: int | None = None
    note: str | None = Field(default=None, max_length=300)


class AccessorialUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: AccessorialCategory | None = None
    unit: AccessorialUnit | None = None
    amount: Decimal | None = None
    percent: Decimal | None = None
    free_minutes: int | None = None
    free_days: int | None = None
    auto_apply: bool | None = None
    note: str | None = Field(default=None, max_length=300)


class PaginateAccessorialRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__category__equal: Optional[AccessorialCategory] = None
    where__auto_apply__equal: Optional[bool] = None
    where__driver_id__equal: Optional[int] = None
    where__code__i_like: Optional[str] = None
