"""Settlement / ExtraCharge / AuditLog 스키마."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.core.schema import BaseSchema
from app.models.enums import SettlementStatus


class ExtraChargeRequest(BaseSchema):
    type: str = Field(..., max_length=32)
    amount: Decimal
    description: str | None = Field(default=None, max_length=500)


class ExtraChargeResponse(BaseSchema):
    id: str
    settlement_id: str
    type: str
    amount: Decimal
    description: str | None
    created_at: datetime


class SettlementCalculateRequest(BaseSchema):
    system_total: Decimal
    extra_charges: list[ExtraChargeRequest] = Field(default_factory=list)


class SettlementAdjustRequest(BaseSchema):
    final_amount: Decimal | None = None
    driver_reported_amount: Decimal | None = None
    has_flag: bool | None = None
    note: str
    extra_charges: list[ExtraChargeRequest] | None = None


class SettlementApproveRequest(BaseSchema):
    final_amount: Decimal | None = None
    note: str | None = None


class SettlementUnapproveRequest(BaseSchema):
    reason: str = Field(..., min_length=1, max_length=500)


class SettlementResponse(BaseSchema):
    id: str
    tenant_id: str
    leg_id: str
    system_total: Decimal
    driver_reported_amount: Decimal | None
    discrepancy: Decimal | None
    has_flag: bool
    final_amount: Decimal | None
    settlement_status: SettlementStatus
    is_settled: bool
    approved_at: datetime | None
    approved_by: str | None
    unapproved_at: datetime | None
    unapproved_by: str | None
    unapproved_reason: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class AuditLogResponse(BaseSchema):
    id: str
    settlement_id: str
    action: str
    actor_id: str | None
    before: dict | None
    after: dict | None
    reason: str | None
    created_at: datetime
