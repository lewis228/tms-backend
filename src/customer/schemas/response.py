# src/customer/schemas/response.py
from __future__ import annotations
from datetime import date
from typing import Literal, List, Optional
from pydantic import EmailStr

from common.schemas.base import ResponseSchema
from customer.const.status import PartnerKind


class CustomerResponseSchema(ResponseSchema):
    """협력사 단건/목록 공용 응답."""
    id: int
    name: str
    code: str | None = None
    kind: PartnerKind
    billing_address: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    mc_number: str | None = None
    dot_number: str | None = None
    insurance_expires_at: date | None = None
    insurance_doc_url: str | None = None
    w9_doc_url: str | None = None
    payment_terms_days: int | None = None
    zip_id: int | None = None
    note: str | None = None
    is_active: bool


class CustomerDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["customer"] = "customer"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[CustomerResponseSchema] = None
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


class CustomerBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class CustomerBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class CustomerBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
