"""Driver Request/Response 스키마.

생성 시 User 가 함께 만들어지고 임시 비번을 1회 응답에 노출.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.schema import BaseSchema


class DriverCreateRequest(BaseSchema):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=128)
    phone: str | None = None
    license_number: str | None = None
    license_state: str | None = Field(default=None, max_length=8)
    truck_number: str | None = None
    note: str | None = Field(default=None, max_length=500)


class DriverUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    phone: str | None = None
    license_number: str | None = None
    license_state: str | None = Field(default=None, max_length=8)
    truck_number: str | None = None
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class DriverResponse(BaseSchema):
    id: str
    tenant_id: str
    user_id: str
    email: str
    name: str
    phone: str | None
    license_number: str | None
    license_state: str | None
    truck_number: str | None
    is_active: bool
    note: str | None
    created_at: datetime
    updated_at: datetime


class DriverCreatedResponse(DriverResponse):
    """생성 시 1회만 임시 비번 노출."""

    temp_password: str
