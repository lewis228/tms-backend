# src/rate_setting/schemas/response.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from rate_setting.const.rate_type import RateType


class RateSettingResponseSchema(ResponseSchema):
    id: int
    name: str
    rate_type: RateType
    flat_amount: Decimal | None = None
    rate_percent: Decimal | None = None
    rate_per_mile: Decimal | None = None
    effective_date: date
    description: str | None = None
    is_active: bool


class RateSettingDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["rate_setting"] = "rate_setting"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[RateSettingResponseSchema] = None
    error: Optional[str] = None


class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class RateSettingBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class RateSettingBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class RateSettingBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
