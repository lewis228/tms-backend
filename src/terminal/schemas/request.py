# src/terminal/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class TerminalCreateRequest(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    note: str | None = Field(default=None, max_length=3000)


class TerminalUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateTerminalRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__name__i_like: Optional[str] = None
    where__code__i_like: Optional[str] = None


class TerminalBulkCreateRequest(RequestSchema):
    items: List[TerminalCreateRequest] = Field(..., min_length=1, max_length=100)


class TerminalBulkUpdateItem(RequestSchema):
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    note: str | None = Field(default=None, max_length=3000)


class TerminalBulkUpdateRequest(RequestSchema):
    items: List[TerminalBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class TerminalBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
