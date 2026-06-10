# src/leg_layer/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from pydantic import Field

from common.schemas.base import RequestSchema
from leg.const.status import PointType


# ── Add-on (레그에 붙인 부가요금 한 줄 — 중복 가능) ───────────────
class LegAddonCreateRequest(RequestSchema):
    leg_id: int
    addon_id: int  # addon 마스터 타입
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal | None = None
    amount: Decimal | None = None        # None 이면 시스템이 마스터 단가로 자동 채움
    amount_override: Decimal | None = None  # 레거시
    # STP 등 위치형 add-on: 타입 + 그 타입 마스터 하나
    point_type: PointType | None = None
    terminal_id: int | None = None
    location_id: int | None = None
    customer_id: int | None = None
    extra: dict | None = None
    note: str | None = Field(default=None, max_length=300)


class LegAddonUpdateRequest(RequestSchema):
    quantity: Decimal | None = None
    unit_amount: Decimal | None = None
    amount: Decimal | None = None
    amount_override: Decimal | None = None
    point_type: PointType | None = None
    terminal_id: int | None = None
    location_id: int | None = None
    customer_id: int | None = None
    extra: dict | None = None
    note: str | None = Field(default=None, max_length=300)
