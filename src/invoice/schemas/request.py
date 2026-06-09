# src/invoice/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Literal

from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from invoice.const.status import InvoiceStatus


class InvoiceCreateRequest(RequestSchema):
    """인보이스 생성. delivery_order_id 주면 그 D/O 컨테이너 원가로 라인 프리필."""
    customer_id: int
    delivery_order_id: Optional[int] = None
    invoice_number: Optional[str] = Field(default=None, max_length=64)
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=500)
    prefill_from_do: bool = True   # delivery_order_id 있으면 컨테이너별 원가 라인 프리필


class InvoiceUpdateRequest(RequestSchema):
    """헤더 수정 (DRAFT 에서만)."""
    invoice_number: Optional[str] = Field(default=None, max_length=64)
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=500)


class InvoiceLineCreateRequest(RequestSchema):
    """청구 라인 추가 (수동)."""
    description: str = Field(min_length=1, max_length=300)
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal = Decimal("0")
    container_id: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=300)


class InvoiceLineUpdateRequest(RequestSchema):
    """청구 라인 수정."""
    description: Optional[str] = Field(default=None, min_length=1, max_length=300)
    quantity: Optional[Decimal] = None
    unit_amount: Optional[Decimal] = None
    note: Optional[str] = Field(default=None, max_length=300)


class InvoiceTransitionRequest(RequestSchema):
    target: InvoiceStatus


class PaginateInvoiceRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__customer_id__equal: Optional[int] = None
    where__delivery_order_id__equal: Optional[int] = None
    where__status__equal: Optional[InvoiceStatus] = None
