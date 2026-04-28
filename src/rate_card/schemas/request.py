# src/rate_card/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from charge_code.const.status import ChargeUnit
from container.const.status import ContainerSize


class RateCardCreateRequest(RequestSchema):
    charge_code_id: int
    name: str | None = Field(default=None, max_length=200)
    scope_customer_id: int | None = None
    scope_terminal_id: int | None = None
    scope_size: ContainerSize | None = None
    scope_zone: str | None = Field(default=None, max_length=64)
    scope_from_location_id: int | None = None
    scope_to_location_id: int | None = None
    unit: ChargeUnit = ChargeUnit.FLAT
    amount: Decimal | None = None
    percent: Decimal | None = None
    per_unit: Decimal | None = None
    effective_from: date
    effective_to: date | None = None
    priority: int = 0
    description: str | None = Field(default=None, max_length=3000)


class RateCardUpdateRequest(RequestSchema):
    charge_code_id: int | None = None
    name: str | None = Field(default=None, max_length=200)
    scope_customer_id: int | None = None
    scope_terminal_id: int | None = None
    scope_size: ContainerSize | None = None
    scope_zone: str | None = Field(default=None, max_length=64)
    scope_from_location_id: int | None = None
    scope_to_location_id: int | None = None
    unit: ChargeUnit | None = None
    amount: Decimal | None = None
    percent: Decimal | None = None
    per_unit: Decimal | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    priority: int | None = None
    description: str | None = Field(default=None, max_length=3000)


class PaginateRateCardRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__charge_code_id__equal: Optional[int] = None
    where__scope_customer_id__equal: Optional[int] = None
    where__scope_terminal_id__equal: Optional[int] = None


class RateCardBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
