# src/driver/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class DriverCreateRequest(RequestSchema):
    """기사 생성 — User 행도 함께 만들어진다 (service 가 처리)."""
    user_id: int  # 이미 생성된 User.id (DRIVER role) 와 link
    license_number: str | None = Field(default=None, max_length=64)
    license_state: str | None = Field(default=None, max_length=8)
    truck_number: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=3000)


class DriverUpdateRequest(RequestSchema):
    license_number: str | None = Field(default=None, max_length=64)
    license_state: str | None = Field(default=None, max_length=8)
    truck_number: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=3000)


class PaginateDriverRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__truck_number__i_like: Optional[str] = None
    where__license_number__i_like: Optional[str] = None


class DriverBulkCreateRequest(RequestSchema):
    items: List[DriverCreateRequest] = Field(..., min_length=1, max_length=100)


class DriverBulkUpdateItem(RequestSchema):
    id: int
    license_number: str | None = Field(default=None, max_length=64)
    license_state: str | None = Field(default=None, max_length=8)
    truck_number: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=3000)


class DriverBulkUpdateRequest(RequestSchema):
    items: List[DriverBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class DriverBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
