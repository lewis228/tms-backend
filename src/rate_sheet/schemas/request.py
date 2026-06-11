# src/rate_sheet/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, model_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from rate_sheet.const.status import (
    SheetKind, RateMoveType, RateServiceType, RateEntrySource,
)


class RateSheetCreateRequest(RequestSchema):
    """Rate Sheet(슬롯) 생성 DTO — (group, kind, move_type, service_type).

    - ZIP/CITY: move_type 필요 (service_type 선택)
    - MILE/HOURLY: move_type/service_type 없음(per_unit 단일 셀)
    """
    rate_group_id: int
    kind: SheetKind
    move_type: RateMoveType | None = None
    service_type: RateServiceType | None = None
    note: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def _validate_kind(self):
        if self.kind in {SheetKind.ZIP, SheetKind.CITY}:
            if self.move_type is None:
                raise ValueError("ZIP/CITY 시트는 move_type 이 필요합니다.")
        else:  # MILE / HOURLY
            if self.move_type is not None or self.service_type is not None:
                raise ValueError("MILE/HOURLY 시트는 move_type/service_type 를 가질 수 없습니다.")
        return self


class RateSheetUpdateRequest(RequestSchema):
    """Rate Sheet 헤더 수정 — 슬롯 식별자는 불변, note 만."""
    note: str | None = Field(default=None, max_length=3000)


class PaginateRateSheetRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__rate_group_id__equal: Optional[int] = None
    where__kind__equal: Optional[SheetKind] = None
    where__move_type__equal: Optional[RateMoveType] = None
    where__service_type__equal: Optional[RateServiceType] = None


class SetRateEntryRequest(RequestSchema):
    """요율 셀 값 등록/변경 (유효일자 버전 추가) — 양방향(↔) 구간 좌표.

    셀 좌표 = 양측 각각 원자 1개, 혼합 허용:
    - ZIP:  zip | zone
    - CITY: city(+state) | zone
    - MILE/HOURLY: 좌표 없음, per_unit
    from/to 순서는 의미 없음(저장 시 정규화). 값은 amount 또는 per_unit 중 하나.
    """
    from_zip: str | None = Field(default=None, max_length=16)
    to_zip: str | None = Field(default=None, max_length=16)
    from_zone_id: int | None = None
    to_zone_id: int | None = None
    from_city: str | None = Field(default=None, max_length=120)
    from_state: str | None = Field(default=None, max_length=8)
    to_city: str | None = Field(default=None, max_length=120)
    to_state: str | None = Field(default=None, max_length=8)

    amount: Decimal | None = None
    per_unit: Decimal | None = None

    effective_from: date
    source: RateEntrySource = RateEntrySource.SHEET
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_value(self):
        if self.amount is None and self.per_unit is None:
            raise ValueError("amount 또는 per_unit 중 하나는 필요합니다.")
        if self.amount is not None and self.amount < 0:
            raise ValueError("amount 는 0 이상이어야 합니다.")
        if self.per_unit is not None and self.per_unit < 0:
            raise ValueError("per_unit 은 0 이상이어야 합니다.")
        return self


class BulkSetRateEntryRequest(RequestSchema):
    """그리드 일괄 저장 — 같은 시트의 여러 셀."""
    items: List[SetRateEntryRequest] = Field(..., min_length=1, max_length=2000)


class RateResolvePreviewRequest(RequestSchema):
    """요율 종합 해석 미리보기 (디스패치 미리보기용).

    driver_id → 유효 요율그룹 → method 분기로 단가 해석.
    - MILE: miles 필요 / HOURLY: hours 필요
    - ZIP: move_type + from_zip + dest_zip
    - CITY: move_type + from_city + dest_city(+state) (없으면 zip 에서 파생)
    """
    driver_id: int
    work_date: date
    move_type: RateMoveType | None = None
    service_type: RateServiceType | None = None
    from_zip: str | None = None
    from_city: str | None = None
    from_state: str | None = None
    dest_zip: str | None = None
    dest_city: str | None = None
    dest_state: str | None = None
    miles: Decimal | None = None
    hours: Decimal | None = None
