# src/vessel/schemas/response.py
from __future__ import annotations
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema


class VesselResponseSchema(ResponseSchema):
    id: int
    name: str
    imo_number: str | None = None
    line: str | None = None
    note: str | None = None
    is_active: bool


class VesselDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["vessel"] = "vessel"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[VesselResponseSchema] = None
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


class VesselBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class VesselBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class VesselBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
