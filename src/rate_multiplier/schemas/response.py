# src/rate_multiplier/schemas/response.py
from __future__ import annotations
from decimal import Decimal
from typing import Literal

from common.schemas.base import ResponseSchema
from rate_sheet.const.status import RateContainerSize


class RateMultiplierResponseSchema(ResponseSchema):
    id: int
    rate_group_id: int | None = None
    container_size: RateContainerSize
    factor: Decimal
    note: str | None = None
    is_active: bool


class RateMultiplierDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["rate_multiplier"] = "rate_multiplier"
    deleted: bool = True
    soft_deleted: bool = False
