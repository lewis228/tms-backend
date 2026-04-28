# src/charge_code/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from charge_code.const.status import ChargeKind, ChargeUnit


class ChargeCodeCreateRequest(RequestSchema):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    kind: ChargeKind
    default_unit: ChargeUnit = ChargeUnit.FLAT
    default_amount: Decimal | None = None
    is_billable_to_customer: bool = True
    is_payable_to_driver: bool = False
    gl_account: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=3000)


class ChargeCodeUpdateRequest(RequestSchema):
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: ChargeKind | None = None
    default_unit: ChargeUnit | None = None
    default_amount: Decimal | None = None
    is_billable_to_customer: bool | None = None
    is_payable_to_driver: bool | None = None
    gl_account: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=3000)


class PaginateChargeCodeRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__code__i_like: Optional[str] = None
    where__name__i_like: Optional[str] = None
    where__kind__equal: Optional[ChargeKind] = None


class ChargeCodeBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
