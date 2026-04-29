# src/leg_charge/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from charge_code.const.status import ChargeUnit, ChargeSource, PartyKind


class LegChargeCreateRequest(RequestSchema):
    leg_id: int
    charge_code_id: int
    rate_card_id: int | None = None
    # v3: amount = snapshot_unit_amount × quantity. amount 미입력 시 자동 계산.
    amount: Decimal | None = None
    snapshot_unit_amount: Decimal | None = None  # 미입력 시 ChargeCode.default_amount 사용
    quantity: Decimal | None = None              # default 1
    unit: ChargeUnit | None = None
    source: ChargeSource = ChargeSource.MANUAL
    description: str | None = Field(default=None, max_length=3000)
    payee_kind: PartyKind | None = None
    payee_partner_id: int | None = None
    payee_driver_id: int | None = None
    payee_pool_id: int | None = None
    payer_kind: PartyKind | None = None
    payer_partner_id: int | None = None


class LegChargeUpdateRequest(RequestSchema):
    charge_code_id: int | None = None
    amount: Decimal | None = None
    snapshot_unit_amount: Decimal | None = None
    quantity: Decimal | None = None
    unit: ChargeUnit | None = None
    description: str | None = Field(default=None, max_length=3000)
    payee_kind: PartyKind | None = None
    payee_partner_id: int | None = None
    payee_driver_id: int | None = None
    payee_pool_id: int | None = None
    payer_kind: PartyKind | None = None
    payer_partner_id: int | None = None


class PaginateLegChargeRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__leg_id__equal: Optional[int] = None
    where__charge_code_id__equal: Optional[int] = None
    where__settlement_id__equal: Optional[int] = None
    where__source__equal: Optional[ChargeSource] = None


class LegChargeBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
