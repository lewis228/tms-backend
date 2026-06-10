# src/leg_layer/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from pydantic import Field

from common.schemas.base import RequestSchema
from leg_layer.const.status import LegAddonCode


# ── Add-on (추가요금 한 줄 — 중복 가능) ───────────────────────
class LegAddonCreateRequest(RequestSchema):
    leg_id: int
    code: LegAddonCode
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal | None = None
    amount: Decimal | None = None        # None 이면 시스템이 마스터 단가로 자동 채움
    amount_override: Decimal | None = None  # 레거시
    extra: dict | None = None
    note: str | None = Field(default=None, max_length=300)


class LegAddonUpdateRequest(RequestSchema):
    quantity: Decimal | None = None
    unit_amount: Decimal | None = None
    amount: Decimal | None = None
    amount_override: Decimal | None = None
    extra: dict | None = None
    note: str | None = Field(default=None, max_length=300)
