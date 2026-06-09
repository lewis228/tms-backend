# src/invoice/schemas/response.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Literal, List

from pydantic import computed_field

from common.schemas.base import ResponseSchema
from invoice.const.status import InvoiceStatus, InvoiceLineSource


class InvoiceLineResponseSchema(ResponseSchema):
    id: int
    container_id: int | None = None
    description: str
    quantity: Decimal
    unit_amount: Decimal
    amount: Decimal
    source: InvoiceLineSource
    cost_amount: Decimal | None = None
    note: str | None = None


class InvoiceSummarySchema(ResponseSchema):
    """목록/sync 용 (lines 미포함)."""
    id: int
    customer_id: int
    delivery_order_id: int | None = None
    invoice_number: str | None = None
    status: InvoiceStatus
    issue_date: date | None = None
    due_date: date | None = None
    cost_total: Decimal
    charge_total: Decimal
    note: str | None = None
    is_active: bool

    @computed_field
    @property
    def margin(self) -> Decimal:
        return self.charge_total - self.cost_total


class InvoiceDetailSchema(InvoiceSummarySchema):
    lines: List[InvoiceLineResponseSchema] = []


class InvoiceDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["invoice"] = "invoice"
    deleted: bool = True
    soft_deleted: bool = False
