"""Tenant Request/Response 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.schema import BaseSchema


class TenantCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    plan_tier: str = "basic"
    timezone: str = "UTC"
    contact_email: EmailStr | None = None
    contact_phone: str | None = None


class TenantUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    plan_tier: str | None = None
    timezone: str | None = None
    is_active: bool | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None


class TenantResponse(BaseSchema):
    id: str
    name: str
    slug: str
    plan_tier: str
    is_active: bool
    timezone: str
    contact_email: str | None
    contact_phone: str | None
    created_at: datetime
    updated_at: datetime
