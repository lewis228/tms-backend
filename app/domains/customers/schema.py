"""Customer 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.schema import BaseSchema


class CustomerCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    billing_address: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    note: str | None = Field(default=None, max_length=500)


class CustomerUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    billing_address: str | None = None
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class CustomerResponse(BaseSchema):
    id: str
    tenant_id: str
    name: str
    code: str | None
    billing_address: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    is_active: bool
    note: str | None
    created_at: datetime
    updated_at: datetime
