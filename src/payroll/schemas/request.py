# src/payroll/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Literal
from pydantic import Field, model_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from payroll.const.status import PayrollStatus


class PayrollBuildRequest(RequestSchema):
    """드라이버 × 기간 정산 생성/미리보기."""
    driver_id: int
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def _check(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end 는 period_start 이후여야 합니다.")
        return self


class PayrollBuildPeriodRequest(RequestSchema):
    """격주 일괄 정산 — 기간 내 대상 leg 있는 드라이버 전체(또는 지정 목록) 생성."""
    period_start: date
    period_end: date
    driver_ids: Optional[list[int]] = None   # None 이면 대상 leg 있는 드라이버 전체

    @model_validator(mode="after")
    def _check(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end 는 period_start 이후여야 합니다.")
        return self


class PayrollChargeAddRequest(RequestSchema):
    """정산에 addon 추가."""
    code: str = Field(min_length=1, max_length=48)
    addon_id: int | None = None
    snapshot_unit_amount: Decimal | None = None
    quantity: Decimal = Decimal("1")
    amount: Decimal
    note: str | None = Field(default=None, max_length=300)


class PaginatePayrollRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__driver_id__equal: Optional[int] = None
    where__status__equal: Optional[PayrollStatus] = None
