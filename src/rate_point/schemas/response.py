# src/rate_point/schemas/response.py
from __future__ import annotations
from decimal import Decimal
from typing import Literal, List, Optional

from common.schemas.base import ResponseSchema
from rate_point.const.status import PointType


class RatePointResponseSchema(ResponseSchema):
    """Rate Point 단건/목록 공용 응답."""
    id: int
    name: str
    code: str | None = None
    point_type: PointType
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    terminal_id: int | None = None
    location_id: int | None = None
    note: str | None = None
    is_active: bool


class RatePointDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["rate_point"] = "rate_point"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[RatePointResponseSchema] = None
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


class RatePointBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class RatePointBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class RatePointBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
