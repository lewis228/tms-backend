# src/driver_rate_assignment/schemas/request.py
from __future__ import annotations
from datetime import date
from typing import Optional, Literal
from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class DriverRateAssignmentCreateRequest(RequestSchema):
    """Driver Rate Assignment 생성 DTO."""
    driver_id: int
    rate_group_id: int
    effective_from: date
    effective_to: date | None = None
    note: str | None = Field(default=None, max_length=3000)


class DriverRateAssignmentUpdateRequest(RequestSchema):
    """Driver Rate Assignment 수정 DTO (부분 수정 허용)."""
    rate_group_id: int | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateDriverRateAssignmentRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'

    include_inactive: bool = False

    where__driver_id__equal: Optional[int] = None
    where__rate_group_id__equal: Optional[int] = None
