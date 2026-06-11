# src/addon/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal
from pydantic import Field, model_validator

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
    where__code__i_like: Optional[str] = None


class AddonDriverRateUpsertRequest(RequestSchema):
    """기사별 add-on 금액 override 업서트 — 마스터 정의는 그대로, 금액만."""
    amount: Decimal | None = None
    percent: Decimal | None = None
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _validate_value(self):
        if self.amount is None and self.percent is None:
            raise ValueError("amount 또는 percent 중 하나는 필요합니다.")
        if self.amount is not None and self.amount < 0:
            raise ValueError("amount 는 0 이상이어야 합니다.")
        if self.percent is not None and self.percent < 0:
            raise ValueError("percent 는 0 이상이어야 합니다.")
        return self
