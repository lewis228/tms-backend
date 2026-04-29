# src/rate_tariff/schemas/response.py
from __future__ import annotations
from datetime import date
from decimal import Decimal

from common.schemas.base import ResponseSchema
from container.const.status import ContainerSize
from leg.const.status import MoveTypeV3


class RateTariffResponseSchema(ResponseSchema):
    id: int
    name: str
    move_type: MoveTypeV3 | None = None
    container_size: ContainerSize | None = None
    customer_id: int | None = None
    per_value: Decimal
    per_min:   Decimal
    flat_base: Decimal
    effective_from: date
    effective_to: date | None = None
    priority: int
    description: str | None = None
    is_active: bool
