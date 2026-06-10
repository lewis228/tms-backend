# src/addon/schemas/response.py
from __future__ import annotations
from decimal import Decimal
from typing import Literal

from common.schemas.base import ResponseSchema
from addon.const.status import AddonCategory, AddonUnit


class AddonResponseSchema(ResponseSchema):
    id: int
    code: str
    name: str
    category: AddonCategory
    unit: AddonUnit
    amount: Decimal | None = None
    percent: Decimal | None = None
    free_minutes: int | None = None
    free_days: int | None = None
    auto_apply: bool
    is_system: bool
    is_billable_to_customer: bool = True
    is_payable_to_driver: bool = True
    driver_id: int | None = None
    note: str | None = None
    is_active: bool


class AddonDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["addon"] = "addon"
    deleted: bool = True
    soft_deleted: bool = False


class AddonSeedResultSchema(ResponseSchema):
    created: int
    skipped: int
