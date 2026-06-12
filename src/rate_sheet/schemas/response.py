# src/rate_sheet/schemas/response.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, List

from common.schemas.base import ResponseSchema
from rate_sheet.const.status import (
    SheetKind, RateMoveType, RateServiceType, RateEntrySource, RateEntryAction, SheetStatus,
)


class RateSheetResponseSchema(ResponseSchema):
    """Rate Sheet(슬롯) 응답. status/entry_count 는 서비스가 계산."""
    id: int
    rate_group_id: int
    kind: SheetKind
    move_type: RateMoveType | None = None
    service_type: RateServiceType | None = None
    note: str | None = None
    is_active: bool
    status: SheetStatus = SheetStatus.EMPTY
    open_entry_count: int = 0


class RateEntryResponseSchema(ResponseSchema):
    id: int
    rate_sheet_id: int
    from_zip: str | None = None
    to_zip: str | None = None
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
    source: RateEntrySource
    change_reason: str | None = None
    is_active: bool


class RateSheetDetailResponseSchema(RateSheetResponseSchema):
    """시트 + 현재 유효 셀들 (그리드 렌더용)."""
    entries: List[RateEntryResponseSchema] = []


class RateSheetDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["rate_sheet"] = "rate_sheet"
    deleted: bool = True
    soft_deleted: bool = False


class RateEntryHistoryResponseSchema(ResponseSchema):
    id: int
    rate_sheet_id: int
    rate_entry_id: int | None = None
    from_zip: str | None = None
    to_zip: str | None = None
    from_zone_id: int | None = None
    to_zone_id: int | None = None
    from_city: str | None = None
    from_state: str | None = None
    to_city: str | None = None
    to_state: str | None = None
    old_amount: Decimal | None = None
    new_amount: Decimal | None = None
    old_per_unit: Decimal | None = None
    new_per_unit: Decimal | None = None
    effective_from: date | None = None
    action: RateEntryAction
    reason: str | None = None
    created_at: datetime | None = None


class RateLookupResultSchema(ResponseSchema):
    """work_date 기준 셀 조회 결과 (미등록이면 found=False + 경고)."""
    found: bool
    amount: Decimal | None = None
    per_unit: Decimal | None = None
    rate_entry_id: int | None = None
    effective_from: date | None = None
    effective_to: date | None = None  # None = 현재 유효(무제한)
    message: str | None = None


class RateResolveResultSchema(ResponseSchema):
    """요율 종합 해석 결과 — 정산 snapshot 의 원천.

    base_amount = (MILE/HOURLY: per_unit×quantity) | (ZIP/CITY: 매트릭스 셀 amount).
    found=False 면 message 로 사유(디폴트 그룹 없음 / 시트 없음 / 사다리 미해석 등).
    match_step = 해석 사다리 단계 기록(정산 근거 스냅샷·preview 표시용):
    ATOM_ATOM(①) | ATOM_ZONE(②) | ZONE_ZONE(③) | UNIT(MILE/HOURLY).
    """
    found: bool
    method: str | None = None
    rate_group_id: int | None = None
    rate_sheet_id: int | None = None
    rate_entry_id: int | None = None
    zone_id: int | None = None           # 매칭에 실제 사용된 존 (①ATOM_ATOM/UNIT 은 None)
    amount: Decimal | None = None        # 매트릭스 셀 원단가
    per_unit: Decimal | None = None      # MILE/HOURLY 단가
    quantity: Decimal | None = None      # miles / hours
    base_amount: Decimal | None = None   # 최종 산출 (정산 base)
    match_step: str | None = None        # 사다리 단계 (ATOM_ATOM/ATOM_ZONE/ZONE_ZONE/UNIT)
    via_default_group: bool = False      # 사다리 ④ — 디폴트 그룹 폴백으로 해석됨
    assignment_fallback: bool = False    # 기사 미배정/미지정 → ZIP 디폴트 그룹 적용됨
    effective_from: date | None = None   # 매칭된 요율 버전의 유효 시작일
    effective_to: date | None = None     # None = 현재 유효
    message: str | None = None
