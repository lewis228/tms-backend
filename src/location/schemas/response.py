# src/location/schemas/response.py
from __future__ import annotations
from decimal import Decimal
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from location.const.kind import LocationKind


class LocationResponseSchema(ResponseSchema):
    id: int
    name: str
    kind: LocationKind
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    customer_id: int | None = None
    note: str | None = None
    is_active: bool


class LocationDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["location"] = "location"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[LocationResponseSchema] = None
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


class LocationBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class LocationBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class LocationBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
