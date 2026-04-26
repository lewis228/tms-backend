# src/driver/schemas/response.py
from __future__ import annotations
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema


class DriverResponseSchema(ResponseSchema):
    id: int
    user_id: int
    license_number: str | None = None
    license_state: str | None = None
    truck_number: str | None = None
    note: str | None = None
    is_active: bool


class DriverDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["driver"] = "driver"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[DriverResponseSchema] = None
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


class DriverBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class DriverBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class DriverBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
