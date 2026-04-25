"""Auth Request/Response 스키마."""
from __future__ import annotations

from pydantic import EmailStr, Field

from app.core.schema import BaseSchema
from app.models.enums import UserRole


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseSchema):
    refresh_token: str


class TokenPair(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str | None
    role: UserRole
    must_change_password: bool
