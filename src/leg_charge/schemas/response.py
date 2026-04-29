# src/leg_charge/schemas/response.py
from __future__ import annotations
from decimal import Decimal
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from charge_code.const.status import ChargeUnit, ChargeSource, PartyKind


class LegChargeResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    charge_code_id: int
    rate_card_id: int | None = None
    amount: Decimal
    snapshot_unit_amount: Decimal | None = None
    quantity: Decimal | None = None
    unit: ChargeUnit | None = None
    source: ChargeSource
    description: str | None = None
    settlement_id: int | None = None
    is_settled: bool
    payee_kind: PartyKind | None = None
    payee_partner_id: int | None = None
    payee_driver_id: int | None = None
    payee_pool_id: int | None = None
    payer_kind: PartyKind | None = None
    payer_partner_id: int | None = None
    is_active: bool


class LegChargeDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["leg_charge"] = "leg_charge"
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


class LegChargeBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
