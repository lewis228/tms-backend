# src/street_turn/schemas/response.py
from __future__ import annotations
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from street_turn.const.link_type import StreetTurnLinkType


class StreetTurnResponseSchema(ResponseSchema):
    id: int
    import_order_id: int
    export_order_id: int
    container_number: str
    link_type: StreetTurnLinkType
    is_active: bool


class StreetTurnDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["street_turn"] = "street_turn"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[StreetTurnResponseSchema] = None
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


class StreetTurnBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class StreetTurnBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class StreetTurnBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
