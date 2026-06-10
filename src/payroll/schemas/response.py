# src/payroll/schemas/response.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Literal, List

from common.schemas.base import ResponseSchema
from payroll.const.status import PayrollStatus, PayrollLineSource


class PayrollLineResponseSchema(ResponseSchema):
    id: int
    leg_id: int | None = None
    work_date: date | None = None
    base_amount: Decimal
    source: PayrollLineSource
    rate_snapshot: dict | None = None
    message: str | None = None


class PayrollChargeResponseSchema(ResponseSchema):
    id: int
    code: str
    addon_id: int | None = None
    snapshot_unit_amount: Decimal | None = None
    quantity: Decimal
    amount: Decimal
    note: str | None = None


class PayrollSummarySchema(ResponseSchema):
    """목록/sync 용 (lines/charges 미포함)."""
    id: int
    driver_id: int
    period_start: date
    period_end: date
    status: PayrollStatus
    base_total: Decimal
    addon_total: Decimal
    grand_total: Decimal
    note: str | None = None
    is_active: bool


class PayrollDetailSchema(PayrollSummarySchema):
    lines: List[PayrollLineResponseSchema] = []
    charges: List[PayrollChargeResponseSchema] = []


class PayrollPreviewLine(ResponseSchema):
    leg_id: int
    work_date: date | None = None
    base_amount: Decimal
    source: PayrollLineSource
    message: str | None = None


class PayrollPreviewSchema(ResponseSchema):
    driver_id: int
    period_start: date
    period_end: date
    line_count: int
    unresolved_count: int
    base_total: Decimal
    lines: List[PayrollPreviewLine] = []


class PayrollDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["payroll_settlement"] = "payroll_settlement"
    deleted: bool = True
    soft_deleted: bool = False


# ── Bi-weekly 집계 (재설계 2c) ───────────────────────────────────
class PayrollPeriodSummarySchema(ResponseSchema):
    """기간(격주 등)과 겹치는 정산 집계."""
    period_start: date
    period_end: date
    count: int                 # 정산 헤더 수
    driver_count: int          # 고유 드라이버 수
    base_total: Decimal
    addon_total: Decimal
    grand_total: Decimal


class PayrollBuildPeriodResultSchema(ResponseSchema):
    """격주 일괄 생성 결과."""
    period_start: date
    period_end: date
    built_count: int           # 새로 생성된 정산 수
    skipped_drivers: List[int] = []   # 정산 대상 leg 없어 건너뛴 driver
    settlements: List[PayrollSummarySchema] = []
