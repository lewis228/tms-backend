# src/rate_group/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal
from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from rate_group.const.status import RateMethod


class RateGroupCreateRequest(RequestSchema):
    """Rate Group 생성 DTO."""
    name: str = Field(min_length=1, max_length=200)
    method: RateMethod
    is_default: bool = False
    is_template: bool = False
    description: str | None = Field(default=None, max_length=3000)


class RateGroupUpdateRequest(RequestSchema):
    """Rate Group 수정 DTO (부분 수정 허용)."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    method: RateMethod | None = None
    is_default: bool | None = None
    is_template: bool | None = None
    description: str | None = Field(default=None, max_length=3000)


class PaginateRateGroupRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'

    include_inactive: bool = False

    where__name__i_like: Optional[str] = None
    where__method__equal: Optional[RateMethod] = None
    where__is_default__equal: Optional[bool] = None
