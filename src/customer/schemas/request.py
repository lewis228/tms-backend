# src/customer/schemas/request.py
from __future__ import annotations
from datetime import date
from typing import Optional, Literal, List
from pydantic import Field, EmailStr, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from customer.const.status import PartnerKind


class CustomerCreateRequest(RequestSchema):
    """협력사 생성 DTO."""
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    kind: PartnerKind = PartnerKind.CUSTOMER
    billing_address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: EmailStr | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=64)
    mc_number: str | None = Field(default=None, max_length=32)
    dot_number: str | None = Field(default=None, max_length=32)
    insurance_expires_at: date | None = None
    insurance_doc_url: str | None = Field(default=None, max_length=500)
    w9_doc_url: str | None = Field(default=None, max_length=500)
    payment_terms_days: int | None = None
    note: str | None = Field(default=None, max_length=3000)


class CustomerUpdateRequest(RequestSchema):
    """협력사 수정 DTO (부분 수정 허용)."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    kind: PartnerKind | None = None
    billing_address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: EmailStr | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=64)
    mc_number: str | None = Field(default=None, max_length=32)
    dot_number: str | None = Field(default=None, max_length=32)
    insurance_expires_at: date | None = None
    insurance_doc_url: str | None = Field(default=None, max_length=500)
    w9_doc_url: str | None = Field(default=None, max_length=500)
    payment_terms_days: int | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateCustomerRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'

    include_inactive: bool = False

    where__name__i_like: Optional[str] = None
    where__code__i_like: Optional[str] = None
    where__contact_email__i_like: Optional[str] = None
    where__contact_phone__i_like: Optional[str] = None
    where__kind__equal: Optional[PartnerKind] = None


class CustomerBulkCreateRequest(RequestSchema):
    items: List[CustomerCreateRequest] = Field(..., min_length=1, max_length=100)


class CustomerBulkUpdateItem(RequestSchema):
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    kind: PartnerKind | None = None
    billing_address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: EmailStr | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=64)
    mc_number: str | None = Field(default=None, max_length=32)
    dot_number: str | None = Field(default=None, max_length=32)
    insurance_expires_at: date | None = None
    payment_terms_days: int | None = None
    note: str | None = Field(default=None, max_length=3000)


class CustomerBulkUpdateRequest(RequestSchema):
    items: List[CustomerBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class CustomerBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
