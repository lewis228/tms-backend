# src/terminal/schemas/response.py
from __future__ import annotations
from decimal import Decimal
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema


class TerminalResponseSchema(ResponseSchema):
    id: int
    name: str
    code: str | None = None
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    zip_id: int | None = None
    note: str | None = None
    is_active: bool


class TerminalDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["terminal"] = "terminal"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[TerminalResponseSchema] = None
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


class TerminalBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class TerminalBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class TerminalBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
