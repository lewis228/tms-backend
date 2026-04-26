# src/street_turn/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from street_turn.const.link_type import StreetTurnLinkType


class StreetTurnCreateRequest(RequestSchema):
    import_order_id: int
    export_order_id: int
    link_type: StreetTurnLinkType = StreetTurnLinkType.MANUAL


class StreetTurnUpdateRequest(RequestSchema):
    """Street turn 은 거의 immutable. link_type 만 변경 허용."""
    link_type: StreetTurnLinkType | None = None


class PaginateStreetTurnRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__import_order_id__equal: Optional[int] = None
    where__export_order_id__equal: Optional[int] = None
    where__container_number__equal: Optional[str] = None
    where__link_type__equal: Optional[StreetTurnLinkType] = None


class StreetTurnBulkCreateRequest(RequestSchema):
    items: List[StreetTurnCreateRequest] = Field(..., min_length=1, max_length=100)


class StreetTurnBulkUpdateItem(StreetTurnUpdateRequest):
    id: int


class StreetTurnBulkUpdateRequest(RequestSchema):
    items: List[StreetTurnBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class StreetTurnBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
