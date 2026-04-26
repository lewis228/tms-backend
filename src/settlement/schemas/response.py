# src/settlement/schemas/response.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Literal, List, Optional, Any
from common.schemas.base import ResponseSchema
from settlement.const.status import SettlementStatus, SettlementAuditAction


class ExtraChargeResponseSchema(ResponseSchema):
    id: int
    settlement_id: int
    type: str
    amount: Decimal
    description: str | None = None
    is_active: bool


class SettlementResponseSchema(ResponseSchema):
    id: int
    leg_id: int
    settlement_status: SettlementStatus
    system_total: Decimal | None = None
    driver_reported_amount: Decimal | None = None
    discrepancy: Decimal | None = None
    has_flag: bool
    final_amount: Decimal | None = None
    is_settled: bool
    approved_at: datetime | None = None
    approved_by: int | None = None
    unapproved_at: datetime | None = None
    unapproved_by: int | None = None
    unapproved_reason: str | None = None
    note: str | None = None
    is_active: bool


class SettlementAuditLogResponseSchema(ResponseSchema):
    id: int
    settlement_id: int
    action: SettlementAuditAction
    actor_id: int | None = None
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    reason: str | None = None
    created_at: datetime
    is_active: bool


class SettlementDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["settlement"] = "settlement"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[SettlementResponseSchema] = None
    error: Optional[str] = None


class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class SettlementBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class SettlementBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class SettlementBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
