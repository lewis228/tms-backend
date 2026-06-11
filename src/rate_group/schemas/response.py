# src/rate_group/schemas/response.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Literal, List

from common.schemas.base import ResponseSchema
from rate_group.const.status import RateMethod
from rate_sheet.const.status import SheetKind, RateMoveType, RateServiceType


class RateGroupResponseSchema(ResponseSchema):
    """Rate Group 단건/목록 공용 응답."""
    id: int
    name: str
    method: RateMethod
    is_default: bool
    is_template: bool
    description: str | None = None
    is_active: bool


class RateGroupDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["rate_group"] = "rate_group"
    deleted: bool = True
    soft_deleted: bool = False


class FlatRateEntrySchema(ResponseSchema):
    """그룹의 셀 1건을 플랫 행으로(리스트 뷰/매트릭스 피벗 공용). sheet 메타 + 셀 좌표 + 값."""
    rate_entry_id: int
    rate_sheet_id: int
    kind: SheetKind
    move_type: RateMoveType | None = None
    service_type: RateServiceType | None = None
    from_zone_id: int | None = None
    to_zone_id: int | None = None
    from_city: str | None = None
    from_state: str | None = None
    to_city: str | None = None
    to_state: str | None = None
    amount: Decimal | None = None
    per_unit: Decimal | None = None
    effective_from: date
    effective_to: date | None = None


class RateGroupEntriesResponse(ResponseSchema):
    """그룹의 모든 시트 셀을 플랫 행으로 묶은 리스트 뷰 응답."""
    rate_group_id: int
    method: RateMethod
    rows: List[FlatRateEntrySchema] = []
