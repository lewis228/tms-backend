# src/rate_card/schemas/response.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from charge_code.const.status import ChargeUnit
from container.const.status import ContainerSize


class RateCardResponseSchema(ResponseSchema):
    id: int
    charge_code_id: int
    name: str | None = None
    scope_customer_id: int | None = None
    scope_terminal_id: int | None = None
    scope_size: ContainerSize | None = None
    scope_zone: str | None = None
    scope_from_location_id: int | None = None
    scope_to_location_id: int | None = None
    unit: ChargeUnit
    amount: Decimal | None = None
    percent: Decimal | None = None
    per_unit: Decimal | None = None
    effective_from: date
    effective_to: date | None = None
    priority: int
    description: str | None = None
    is_active: bool


class RateCardDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["rate_card"] = "rate_card"
    deleted: bool = True
    soft_deleted: bool = False


class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class RateCardBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
