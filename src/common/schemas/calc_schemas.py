# src/common/schemas/calc_schemas.py
"""라인 금액 계산 미리보기용 요청/응답 스키마."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import Field

from common.schemas.base import RequestSchema, ResponseSchema


class CalcLineRequestSchema(RequestSchema):
    """단일 라인 계산 요청."""
    qty: Decimal = Field(gt=0)
    unit_price: Decimal
    discount_policy_id: Optional[int] = None
    tax_policy_id: Optional[int] = None
    existing_line_id: Optional[int] = None  # 수정 모드: 기존 라인 ID (변경 안 된 필드는 기존 스냅샷 사용)


class CalcLineResponseSchema(ResponseSchema):
    """단일 라인 계산 결과."""
    subtotal_excl_tax: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_incl_tax: Decimal
