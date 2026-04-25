from __future__ import annotations
from pydantic import EmailStr, Field
from common.schemas.base import RequestSchema


class RegisterUserRequestSchema(RequestSchema):
    email: EmailStr
    password: str = Field(min_length=8)
    request_id: str = Field(min_length=8)


class RegisterEmailCodeSendRequestSchema(RequestSchema):
    email: EmailStr


class RegisterEmailCodeVerifyRequestSchema(RequestSchema):
    email: EmailStr
    request_id: str = Field(min_length=8)
    code: str = Field(min_length=6, max_length=6)


class PasswordResetSendCodeRequestSchema(RequestSchema):
    email: EmailStr


class PasswordResetVerifyCodeRequestSchema(RequestSchema):
    email: EmailStr
    request_id: str = Field(min_length=8)
    code: str = Field(min_length=6, max_length=6)


class PasswordResetConfirmRequestSchema(RequestSchema):
    email: EmailStr
    request_id: str = Field(min_length=8)
    new_password: str = Field(min_length=8)
