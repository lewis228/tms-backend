from __future__ import annotations
from typing import Optional
from common.schemas.base import ResponseSchema


class TokenResponseSchema(ResponseSchema):
    access_token: str
    refresh_token: Optional[str] = None


class AccessTokenOnlyResponseSchema(ResponseSchema):
    access_token: str


class RefreshTokenOnlyResponseSchema(ResponseSchema):
    refresh_token: str


class PasswordCodeSendResponseSchema(ResponseSchema):
    request_id: str
    expires_in_sec: int


class PasswordCodeVerifyResponseSchema(ResponseSchema):
    request_id: str


class PasswordResetConfirmResponseSchema(ResponseSchema):
    ok: bool = True
