# src/addon/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal
from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from addon.const.status import AddonCategory, AddonUnit


class AddonCreateRequest(RequestSchema):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=120)
    category: AddonCategory
    unit: AddonUnit
    amount: Decimal | None = None
    percent: Decimal | None = None
    free_minutes: int | None = None
    free_days: int | None = None
    auto_apply: bool = False
    is_billable_to_customer: bool = True
    is_payable_to_driver: bool = True
    driver_id: int | None = None
    note: str | None = Field(default=None, max_length=300)


class AddonUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: AddonCategory | None = None
    unit: AddonUnit | None = None
    amount: Decimal | None = None
    percent: Decimal | None = None
    free_minutes: int | None = None
    free_days: int | None = None
    auto_apply: bool | None = None
    is_billable_to_customer: bool | None = None
    is_payable_to_driver: bool | None = None
    note: str | None = Field(default=None, max_length=300)


class PaginateAddonRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__category__equal: Optional[AddonCategory] = None
    where__auto_apply__equal: Optional[bool] = None
    where__driver_id__equal: Optional[int] = None
    where__code__i_like: Optional[str] = None
