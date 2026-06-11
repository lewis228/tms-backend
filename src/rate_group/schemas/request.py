# src/rate_group/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, model_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from rate_group.const.status import RateMethod
from rate_sheet.const.status import RateMoveType, RateServiceType, RateEntrySource


class RateGroupCreateRequest(RequestSchema):
    """Rate Group 생성 DTO."""
    name: str = Field(min_length=1, max_length=200)
    method: RateMethod
    is_default: bool = False
    # 커스텀 그룹: True(기본)=미등록 구간을 디폴트 그룹으로 폴백(상속), False=빈 그룹
    inherits_default: bool = True
    is_template: bool = False
    description: str | None = Field(default=None, max_length=3000)


class RateGroupUpdateRequest(RequestSchema):
    """Rate Group 수정 DTO (부분 수정 허용)."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    method: RateMethod | None = None
    is_default: bool | None = None
    inherits_default: bool | None = None
    is_template: bool | None = None
    description: str | None = Field(default=None, max_length=3000)


class PaginateRateGroupRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'

    include_inactive: bool = False

    where__name__i_like: Optional[str] = None
    where__method__equal: Optional[RateMethod] = None
    where__is_default__equal: Optional[bool] = None


class FlatRateEntryRequest(RequestSchema):
    """그룹 단위 플랫 행 입력 — 내부적으로 (group, kind, move, service) 시트로 라우팅.

    셀 좌표 = 양측(from/to) 각각 원자 1개 — 혼합 허용(예: from_zip + to_zone_id).
    - ZIP:  move_type 필요 + 양측 각각 zip | zone 중 1개
    - CITY: move_type 필요 + 양측 각각 city(+state) | zone 중 1개
    - MILE/HOURLY: move/service·좌표 없음, per_unit 만
    구간은 양방향(↔) — 저장 시 정규화되므로 from/to 순서는 의미 없음.
    값은 amount(매트릭스) 또는 per_unit(MILE/HOURLY) 중 하나.
    """
    move_type: RateMoveType | None = None
    service_type: RateServiceType | None = None
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
        # 좌표 side 정합성: 각 측은 zip|zone|city 중 정확히 1개 (또는 MILE/HOURLY 로 양측 0개).
        f_cnt = sum(x is not None for x in (self.from_zip, self.from_zone_id)) + (1 if self.from_city else 0)
        t_cnt = sum(x is not None for x in (self.to_zip, self.to_zone_id)) + (1 if self.to_city else 0)
        if f_cnt > 1 or t_cnt > 1:
            raise ValueError("한 측의 좌표는 zip / zone / city 중 1개만 지정할 수 있습니다.")
        if (f_cnt == 0) != (t_cnt == 0):
            raise ValueError("from 측과 to 측 좌표는 함께 지정해야 합니다 (반쪽 셀 방지).")
        if self.from_state and not self.from_city:
            raise ValueError("from_state 는 from_city 와 함께 지정해야 합니다.")
        if self.to_state and not self.to_city:
            raise ValueError("to_state 는 to_city 와 함께 지정해야 합니다.")
        return self


class BulkFlatRateEntryRequest(RequestSchema):
    """그룹 플랫 행 일괄 입력(Excel/대량)."""
    items: List[FlatRateEntryRequest] = Field(..., min_length=1, max_length=5000)
