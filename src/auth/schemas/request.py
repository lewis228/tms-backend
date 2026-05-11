# src/auth/schemas/request.py
from __future__ import annotations
from pydantic import EmailStr, Field
from common.schemas.base import RequestSchema


class RegisterUserRequestSchema(RequestSchema):
    """최종 회원가입 요청 바디 (이메일 OTP 검증 완료 상태에서 가입)"""
    email: EmailStr
    password: str = Field(min_length=8)
    request_id: str = Field(min_length=8)  #  alias 제거 → snake_case 통일


class RegisterEmailCodeSendRequestSchema(RequestSchema):
    """회원가입용 이메일 OTP 발송 요청"""
    email: EmailStr


class RegisterEmailCodeVerifyRequestSchema(RequestSchema):
    """회원가입용 이메일 OTP 검증 요청"""
    email: EmailStr
    request_id: str = Field(min_length=8)  #  alias 제거
    code: str = Field(min_length=6, max_length=6)


class PasswordResetSendCodeRequestSchema(RequestSchema):
    """비밀번호 재설정 - 이메일 OTP 발송 요청"""
    email: EmailStr


class PasswordResetVerifyCodeRequestSchema(RequestSchema):
    """비밀번호 재설정 - 이메일 OTP 검증 요청"""
    email: EmailStr
    request_id: str = Field(min_length=8)  #  alias 제거
    code: str = Field(min_length=6, max_length=6)


class PasswordResetConfirmRequestSchema(RequestSchema):
    """비밀번호 재설정 - 최종 비밀번호 변경 요청"""
    email: EmailStr
    request_id: str = Field(min_length=8)   #  alias 제거
    new_password: str = Field(min_length=8)  #  alias 제거


# ══════════════════════════════════════════════════════════════════════════
# Driver Mobile (폰번호 OTP)
# ══════════════════════════════════════════════════════════════════════════

class DriverOtpRequestSchema(RequestSchema):
    """기사 모바일 OTP 발송 요청 (폰번호)."""
    phone: str = Field(min_length=8, max_length=30, description="010-1234-5678 또는 +82 형식")


class DriverOtpVerifySchema(RequestSchema):
    """기사 모바일 OTP 검증 요청."""
    phone: str = Field(min_length=8, max_length=30)
    request_id: str = Field(min_length=8)
    code: str = Field(min_length=6, max_length=6)


class DriverLoginSchema(RequestSchema):
    """기사 모바일 최종 로그인 (verify 통과 후)."""
    phone: str = Field(min_length=8, max_length=30)
    request_id: str = Field(min_length=8)