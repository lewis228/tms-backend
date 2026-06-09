# src/accessorial/schemas/response.py
from __future__ import annotations
from decimal import Decimal
from typing import Literal

from common.schemas.base import ResponseSchema
from accessorial.const.status import AccessorialCategory, AccessorialUnit


class AccessorialResponseSchema(ResponseSchema):
    id: int
    code: str
    name: str
    category: AccessorialCategory
    unit: AccessorialUnit
    amount: Decimal | None = None
    percent: Decimal | None = None
    free_minutes: int | None = None
    free_days: int | None = None
    auto_apply: bool
    is_system: bool
    driver_id: int | None = None
    note: str | None = None
    is_active: bool


class AccessorialDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["accessorial"] = "accessorial"
    deleted: bool = True
    soft_deleted: bool = False
