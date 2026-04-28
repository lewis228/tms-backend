# src/driver/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator, EmailStr
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from driver.const.status import EmploymentKind, PaymentTermsKind


class DriverCreateRequest(RequestSchema):
    """기사 생성 — service 가 user 도 자동 생성. truck 은 별도 truck 마스터 (H-3)."""
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=64)
    license_number: str | None = Field(default=None, max_length=64)
    license_state: str | None = Field(default=None, max_length=8)
    note: str | None = Field(default=None, max_length=3000)
    # H-5
    employment_kind: EmploymentKind = EmploymentKind.IN_HOUSE
    carrier_id: int | None = None
    payment_terms_kind: PaymentTermsKind | None = None
    payment_terms_value: Decimal | None = None
    default_truck_id: int | None = None
    default_chassis_id: int | None = None
    license_expires_at: date | None = None
    medical_cert_expires_at: date | None = None


class DriverUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=64)
    license_number: str | None = Field(default=None, max_length=64)
    license_state: str | None = Field(default=None, max_length=8)
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=3000)
    # H-5
    employment_kind: EmploymentKind | None = None
    carrier_id: int | None = None
    payment_terms_kind: PaymentTermsKind | None = None
    payment_terms_value: Decimal | None = None
    default_truck_id: int | None = None
    default_chassis_id: int | None = None
    license_expires_at: date | None = None
    medical_cert_expires_at: date | None = None


class PaginateDriverRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__license_number__i_like: Optional[str] = None
    where__employment_kind__equal: Optional[EmploymentKind] = None
    where__carrier_id__equal: Optional[int] = None


class DriverBulkCreateRequest(RequestSchema):
    items: List[DriverCreateRequest] = Field(..., min_length=1, max_length=100)


class DriverBulkUpdateItem(RequestSchema):
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=64)
    license_number: str | None = Field(default=None, max_length=64)
    license_state: str | None = Field(default=None, max_length=8)
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=3000)


class DriverBulkUpdateRequest(RequestSchema):
    items: List[DriverBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class DriverBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
