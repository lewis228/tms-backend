# src/auth/schemas/response.py
from __future__ import annotations
from typing import Optional
from common.schemas.base import ResponseSchema


class TokenResponseSchema(ResponseSchema):
    """
    로그인/가입 응답:
    - 웹: access_token만 body에, refresh_token은 HttpOnly 쿠키 → None
    - 앱: access_token + refresh_token 모두 body 반환
    """
    access_token: str                      #  snake_case
    refresh_token: Optional[str] = None    #  snake_case


class AccessTokenOnlyResponseSchema(ResponseSchema):
    """access 토큰만 반환"""
    access_token: str                      #  snake_case


class RefreshTokenOnlyResponseSchema(ResponseSchema):
    """refresh 토큰만 반환 (앱·데스크톱 등)"""
    refresh_token: str                     #  snake_case


class PasswordCodeSendResponseSchema(ResponseSchema):
    """이메일 OTP 전송 응답 (비번찾기/회원가입 공용 형태)"""
    request_id: str                        #  snake_case
    expires_in_sec: int                    #  snake_case


class PasswordCodeVerifyResponseSchema(ResponseSchema):
    """이메일 OTP 검증 성공 응답"""
    request_id: str                        #  snake_case


class PasswordResetConfirmResponseSchema(ResponseSchema):
    """비밀번호 재설정 최종 확인 응답"""
    ok: bool = True


# ══════════════════════════════════════════════════════════════════════════
# Driver Mobile (폰번호 OTP)
# ══════════════════════════════════════════════════════════════════════════

class DriverOtpSendResponseSchema(ResponseSchema):
    """기사 모바일 OTP 발송 응답."""
    request_id: str
    expires_in_sec: int


class DriverOtpVerifyResponseSchema(ResponseSchema):
    """기사 모바일 OTP 검증 성공 응답."""
    request_id: str