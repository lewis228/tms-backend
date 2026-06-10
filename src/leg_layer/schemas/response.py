# src/leg_layer/schemas/response.py
from __future__ import annotations
from decimal import Decimal

from common.schemas.base import ResponseSchema
from leg.const.status import PointType


class LegAddonResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    addon_id: int | None = None
    code: str
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal | None = None
    amount: Decimal = Decimal("0")
    amount_override: Decimal | None = None
    is_payable_to_driver: bool = True
    is_billable_to_customer: bool = True
    point_type: PointType | None = None
    terminal_id: int | None = None
    location_id: int | None = None
    customer_id: int | None = None
    extra: dict | None = None
    note: str | None = None
    is_active: bool


class LegLayerDeleteResponseSchema(ResponseSchema):
    id: int
    deleted: bool = True
