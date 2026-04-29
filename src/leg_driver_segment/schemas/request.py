# src/leg_driver_segment/schemas/request.py
from __future__ import annotations
from datetime import datetime

from common.schemas.base import RequestSchema
from leg.const.status import HandoverReason


class LegDriverSegmentCreateRequest(RequestSchema):
    leg_id: int
    driver_id: int
    truck_id: int | None = None
    sequence_no: int | None = None  # 미지정 시 다음 번호
    started_at: datetime | None = None
    ended_at:   datetime | None = None
    handover_reason: HandoverReason | None = None
    note: str | None = None


class LegDriverSegmentUpdateRequest(RequestSchema):
    driver_id: int | None = None
    truck_id: int | None = None
    started_at: datetime | None = None
    ended_at:   datetime | None = None
    handover_reason: HandoverReason | None = None
    note: str | None = None
