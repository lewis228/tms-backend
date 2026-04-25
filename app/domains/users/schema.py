"""User Request/Response 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.schema import BaseSchema
from app.models.enums import UserRole


class UserCreateRequest(BaseSchema):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole
    phone: str | None = None
    tenant_id: str | None = None  # SUPER_ADMIN 만 명시 가능


class UserUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    phone: str | None = None
    is_active: bool | None = None
    role: UserRole | None = None


class PasswordChangeRequest(BaseSchema):
    current_password: str | None = None
    new_password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseSchema):
    id: str
    tenant_id: str | None
    email: str
    name: str
    role: UserRole
    phone: str | None
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
