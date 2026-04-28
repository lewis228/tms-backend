# src/leg_stop/schemas/request.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from leg.const.status import StopKind


class LegStopCreateRequest(RequestSchema):
    leg_id: int
    sequence_no: int
    stop_kind: StopKind
    location_id: int | None = None
    container_id: int | None = None
    chassis_id: int | None = None
    arrived_at: datetime | None = None
    departed_at: datetime | None = None
    note: str | None = Field(default=None, max_length=3000)


class LegStopUpdateRequest(RequestSchema):
    sequence_no: int | None = None
    stop_kind: StopKind | None = None
    location_id: int | None = None
    container_id: int | None = None
    chassis_id: int | None = None
    arrived_at: datetime | None = None
    departed_at: datetime | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateLegStopRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__leg_id__equal: Optional[int] = None
    where__stop_kind__equal: Optional[StopKind] = None


class LegStopBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
