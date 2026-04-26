# src/vessel/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class VesselCreateRequest(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    imo_number: str | None = Field(default=None, max_length=16)
    line: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=3000)


class VesselUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    imo_number: str | None = Field(default=None, max_length=16)
    line: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=3000)


class PaginateVesselRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__name__i_like: Optional[str] = None
    where__imo_number__i_like: Optional[str] = None
    where__line__i_like: Optional[str] = None


class VesselBulkCreateRequest(RequestSchema):
    items: List[VesselCreateRequest] = Field(..., min_length=1, max_length=100)


class VesselBulkUpdateItem(RequestSchema):
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    imo_number: str | None = Field(default=None, max_length=16)
    line: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=3000)


class VesselBulkUpdateRequest(RequestSchema):
    items: List[VesselBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class VesselBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
