# src/chassis_event/schemas/request.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
from pydantic import Field
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from leg.const.status import ChassisEventKind


class ChassisEventCreateRequest(RequestSchema):
    chassis_id: int
    leg_id: int | None = None
    event_kind: ChassisEventKind
    location_id: int | None = None
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=3000)


class PaginateChassisEventRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__chassis_id__equal: Optional[int] = None
    where__leg_id__equal: Optional[int] = None
    where__event_kind__equal: Optional[ChassisEventKind] = None
