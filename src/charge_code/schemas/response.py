# src/charge_code/schemas/response.py
from __future__ import annotations
from decimal import Decimal
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from charge_code.const.status import ChargeKind, ChargeUnit


class ChargeCodeResponseSchema(ResponseSchema):
    id: int
    code: str
    name: str
    kind: ChargeKind
    default_unit: ChargeUnit
    default_amount: Decimal | None = None
    is_billable_to_customer: bool
    is_payable_to_driver: bool
    gl_account: str | None = None
    description: str | None = None
    is_active: bool


class ChargeCodeDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["charge_code"] = "charge_code"
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


class ChargeCodeBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
