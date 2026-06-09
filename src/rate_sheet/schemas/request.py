# src/rate_sheet/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, model_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from rate_sheet.const.status import SheetKind, RateMoveType, RateContainerSize, RateEntrySource


class RateSheetCreateRequest(RequestSchema):
    """Rate Sheet(슬롯) 생성 DTO.

    - POINT_ZONE/POINT_CITY/POINT_POINT: move_type + row_point_id 필요
    - MILE/HOURLY: move_type/row_point_id 없음(per_unit 단일 셀)
    """
    rate_group_id: int
    kind: SheetKind
    move_type: RateMoveType | None = None
    row_point_id: int | None = None
    note: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def _validate_kind(self):
        matrix_kinds = {SheetKind.POINT_ZONE, SheetKind.POINT_CITY, SheetKind.POINT_POINT}
        if self.kind in matrix_kinds:
            if self.move_type is None or self.row_point_id is None:
                raise ValueError("POINT_* 시트는 move_type 과 row_point_id 가 필요합니다.")
        else:  # MILE / HOURLY
            if self.move_type is not None or self.row_point_id is not None:
                raise ValueError("MILE/HOURLY 시트는 move_type/row_point_id 를 가질 수 없습니다.")
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
    where__row_point_id__equal: Optional[int] = None


class SetRateEntryRequest(RequestSchema):
    """요율 셀 값 등록/변경 (유효일자 버전 추가).

    셀 좌표는 시트 kind 에 맞게:
    - POINT_ZONE: col_zone_id (+ container_size)
    - POINT_CITY: col_city (+ col_state, container_size)
    - POINT_POINT: col_point_id (+ container_size, NONE 이면 size 없음)
    - MILE/HOURLY: 좌표 없음, per_unit
    값은 amount(매트릭스/Point×Point) 또는 per_unit(MILE/HOURLY) 중 하나.
    """
    col_zone_id: int | None = None
    col_point_id: int | None = None
    col_city: str | None = Field(default=None, max_length=120)
    col_state: str | None = Field(default=None, max_length=8)
    container_size: RateContainerSize | None = None

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
    """요율 종합 해석 미리보기 (leg 재설계 전 검증/디스패치 미리보기용).

    driver_id → 유효 요율그룹 → method 분기로 단가 해석.
    - MILE: miles 필요 / HOURLY: hours 필요
    - ZONE: move_type+row_point_id + dest_zip + container_size
    - CITY: move_type+row_point_id + dest_city(+dest_state) + container_size
    """
    driver_id: int
    work_date: date
    move_type: RateMoveType | None = None
    row_point_id: int | None = None
    dest_zip: str | None = None
    dest_city: str | None = None
    dest_state: str | None = None
    container_size: RateContainerSize | None = None
    miles: Decimal | None = None
    hours: Decimal | None = None
