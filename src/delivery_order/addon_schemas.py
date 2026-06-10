# src/delivery_order/addon_schemas.py
from __future__ import annotations
from decimal import Decimal
from pydantic import Field

from common.schemas.base import RequestSchema, ResponseSchema


class DoAddonCreateRequest(RequestSchema):
    delivery_order_id: int
    code: str = Field(min_length=1, max_length=48)   # DMR/DET/HZM 등
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal | None = None
    amount: Decimal | None = None        # None 이면 시스템이 마스터 단가로 자동 채움
    note: str | None = Field(default=None, max_length=300)


class DoAddonUpdateRequest(RequestSchema):
    quantity: Decimal | None = None
    unit_amount: Decimal | None = None
    amount: Decimal | None = None
    note: str | None = Field(default=None, max_length=300)


class DoAddonResponseSchema(ResponseSchema):
    id: int
    delivery_order_id: int
    code: str
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal | None = None
    amount: Decimal = Decimal("0")
    note: str | None = None
    is_active: bool


class DoAddonDeleteResponseSchema(ResponseSchema):
    id: int
    deleted: bool = True
