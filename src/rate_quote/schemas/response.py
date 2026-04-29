# src/rate_quote/schemas/response.py
from __future__ import annotations
from datetime import date
from decimal import Decimal

from common.schemas.base import ResponseSchema
from container.const.status import ContainerSize
from leg.const.status import MoveTypeV3


class RateQuoteResponseSchema(ResponseSchema):
    id: int
    name: str | None = None
    origin_location_id: int | None = None
    destination_location_id: int | None = None
    container_size: ContainerSize | None = None
    move_type: MoveTypeV3 | None = None
    customer_id: int | None = None
    fixed_amount: Decimal
    effective_from: date
    effective_to: date | None = None
    priority: int
    description: str | None = None
    is_active: bool
