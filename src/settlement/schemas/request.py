# src/settlement/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from settlement.const.status import SettlementStatus


class ExtraChargeInput(RequestSchema):
    type: str = Field(..., max_length=64)
    amount: Decimal
    description: str | None = Field(default=None, max_length=3000)


class SettlementCreateRequest(RequestSchema):
    """Leg 가 생성될 때 자동 생성되는 게 일반적. 명시 생성도 가능."""
    leg_id: int
    note: str | None = Field(default=None, max_length=3000)


class SettlementCalculateRequest(RequestSchema):
    """PENDING/CALCULATED → CALCULATED. system_total 계산 + extras 입력."""
    system_total: Decimal
    extra_charges: List[ExtraChargeInput] = Field(default_factory=list, max_length=100)


class SettlementAdjustRequest(RequestSchema):
    """CALCULATED/ADJUSTED → ADJUSTED. note 필수, has_flag 자동/수동, extras 재정의."""
    final_amount: Decimal | None = None
    driver_reported_amount: Decimal | None = None
    has_flag: bool = False
    note: str = Field(..., min_length=1, max_length=3000)
    extra_charges: List[ExtraChargeInput] = Field(default_factory=list, max_length=100)


class SettlementApproveRequest(RequestSchema):
    """CALCULATED/ADJUSTED → APPROVED. final_amount 미지정 시 system_total 사용."""
    final_amount: Decimal | None = None
    note: str | None = Field(default=None, max_length=3000)


class SettlementUnapproveRequest(RequestSchema):
    """APPROVED → ADJUSTED. ADMIN+ 권한. reason 필수."""
    reason: str = Field(..., min_length=1, max_length=500)


class SettlementUpdateRequest(RequestSchema):
    """일반 수정 (note 등)."""
    note: str | None = Field(default=None, max_length=3000)


class PaginateSettlementRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__leg_id__equal: Optional[int] = None
    where__settlement_status__equal: Optional[SettlementStatus] = None
    where__has_flag__equal: Optional[bool] = None
    where__is_settled__equal: Optional[bool] = None


class SettlementBulkCreateRequest(RequestSchema):
    items: List[SettlementCreateRequest] = Field(..., min_length=1, max_length=100)


class SettlementBulkUpdateItem(SettlementUpdateRequest):
    id: int


class SettlementBulkUpdateRequest(RequestSchema):
    items: List[SettlementBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class SettlementBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
