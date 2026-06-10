# src/leg_layer/schemas/response.py
from __future__ import annotations
from decimal import Decimal

from common.schemas.base import ResponseSchema
from leg_layer.const.status import LegAddonCode


class LegAddonResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    code: LegAddonCode
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal | None = None
    amount: Decimal = Decimal("0")
    amount_override: Decimal | None = None
    extra: dict | None = None
    note: str | None = None
    is_active: bool


class LegLayerDeleteResponseSchema(ResponseSchema):
    id: int
    deleted: bool = True
