# src/auth/route.py
from __future__ import annotations
import json
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

#  올바른 import
from database.dependencies import get_write_db, get_read_db
from cache.dependencies import get_write_redis, get_read_redis

from auth.service import AuthService
from auth.const.providers import AuthProviderEnum
from auth.oauth.google import GoogleOAuthProvider
from auth.oauth.kakao import KakaoOAuthProvider
from auth.oauth.apple import AppleOAuthProvider
from auth.tokens.basic_token import basic_token  #  basic_auth_credentials 아님!
from auth.schemas.request import (
    RegisterUserRequestSchema,
    RegisterEmailCodeSendRequestSchema,
    RegisterEmailCodeVerifyRequestSchema,
    PasswordResetSendCodeRequestSchema,
    PasswordResetVerifyCodeRequestSchema,
    PasswordResetConfirmRequestSchema,
    DriverOtpRequestSchema,
    DriverOtpVerifySchema,
    DriverLoginSchema,
)
from auth.schemas.response import (
    TokenResponseSchema,
    AccessTokenOnlyResponseSchema,
    RefreshTokenOnlyResponseSchema,
    PasswordCodeSendResponseSchema,
    PasswordCodeVerifyResponseSchema,
    PasswordResetConfirmResponseSchema,
    DriverOtpSendResponseSchema,
    DriverOtpVerifyResponseSchema,
)
from user.schemas.response import UserResponseSchema
from common.const.settings import settings
from common.exceptions.base import AppException

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ══════════════════════════════════════════════════════════════════════════════
# 이메일 로그인 / 로그아웃
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/login", response_model=TokenResponseSchema, summary="로그인 (ID/비밀번호, BasicAuth)")
async def login(
    request: Request,
    response: Response,
    _user: UserResponseSchema = Depends(basic_token),  #  기존 방식 유지
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),  #  올바른 import
):
    """
    이메일/비밀번호 로그인 (Basic Auth)
    
    - BasicAuth 인증 성공 시 `request.state.user`로 사용자 주입됨
    - 웹: access_token만 body, refresh_token은 HttpOnly 쿠키
    - 앱: access_token + refresh_token 모두 body
    """
    auth = AuthService(db, redis)
    user: UserResponseSchema = request.state.user
    return await auth.login_user(request, response, user)


@router.post("/logout", status_code=204, summary="로그아웃")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """로그아웃: 세션/토큰 정리"""
    svc = AuthService(db, redis)
    await svc.logout(request, response)


# ══════════════════════════════════════════════════════════════════════════════
# 토큰 재발급
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/token/access", response_model=AccessTokenOnlyResponseSchema, summary="access 토큰 재발급")
async def issue_access_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_read_redis),
):
    """refresh 토큰으로 새 access 토큰 발급"""
    svc = AuthService(db, redis)
    return await svc.issue_new_access_from_request(request, response)


@router.post("/token/refresh", response_model=RefreshTokenOnlyResponseSchema, summary="refresh 토큰 회전")
async def rotate_refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """refresh 토큰 회전 (앱/데스크톱용)"""
    svc = AuthService(db, redis)
    return await svc.rotate_refresh_from_request(request, response)


# ══════════════════════════════════════════════════════════════════════════════
# 회원가입 (이메일 OTP)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/register/email/request", response_model=PasswordCodeSendResponseSchema, summary="회원가입 - 이메일 OTP 발송")
async def send_signup_email_code(
    body: RegisterEmailCodeSendRequestSchema,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_write_redis),
):
    """회원가입 1단계: 이메일 인증 코드 발송"""
    svc = AuthService(db, redis)
    return await svc.request_signup_email_code(email=body.email)


@router.post("/register/email/verify", response_model=PasswordCodeVerifyResponseSchema, summary="회원가입 - 이메일 OTP 검증")
async def verify_signup_email_code(
    body: RegisterEmailCodeVerifyRequestSchema,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_write_redis),
):
    """회원가입 2단계: 이메일 인증 코드 검증"""
    svc = AuthService(db, redis)
    return await svc.verify_signup_email_code(
        email=body.email,
        request_id=body.request_id,
        code=body.code,
    )


@router.post("/register", response_model=TokenResponseSchema, summary="회원가입 - 최종 가입 후 자동 로그인")
async def register_user(
    request: Request,
    response: Response,
    body: RegisterUserRequestSchema,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """회원가입 3단계: 최종 가입 + 자동 로그인"""
    svc = AuthService(db, redis)
    return await svc.register_and_login_user(request, response, body)


# ══════════════════════════════════════════════════════════════════════════════
# 비밀번호 재설정
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/password/reset/request", response_model=PasswordCodeSendResponseSchema, summary="비밀번호 재설정 - 이메일 OTP 발송")
async def send_password_reset_code(
    body: PasswordResetSendCodeRequestSchema,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_write_redis),
):
    """비밀번호 재설정 1단계: 이메일 인증 코드 발송"""
    svc = AuthService(db, redis)
    return await svc.request_password_reset(email=body.email)


@router.post("/password/reset/verify", response_model=PasswordCodeVerifyResponseSchema, summary="비밀번호 재설정 - 이메일 OTP 검증")
async def verify_password_reset_code(
    body: PasswordResetVerifyCodeRequestSchema,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_write_redis),
):
    """비밀번호 재설정 2단계: 이메일 인증 코드 검증"""
    svc = AuthService(db, redis)
    return await svc.verify_password_code(
        email=body.email,
        request_id=body.request_id,
        code=body.code,
    )


@router.post("/password/reset/confirm", response_model=PasswordResetConfirmResponseSchema, summary="비밀번호 재설정 - 최종 변경")
async def confirm_password_reset(
    body: PasswordResetConfirmRequestSchema,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """비밀번호 재설정 3단계: 최종 비밀번호 변경"""
    svc = AuthService(db, redis)
    return await svc.confirm_password_reset(
        email=body.email,
        request_id=body.request_id,
        new_password=body.new_password,
    )


# ══════════════════════════════════════════════════════════════════════════════
# OAuth 로그인
# ══════════════════════════════════════════════════════════════════════════════

def _get_oauth_provider(provider: str, redis: Redis):
    """OAuth provider 인스턴스 생성"""
    provider_lower = provider.lower()
    
    if provider_lower == AuthProviderEnum.GOOGLE.value:
        return GoogleOAuthProvider(redis)
    elif provider_lower == AuthProviderEnum.KAKAO.value:
        return KakaoOAuthProvider(redis)
    elif provider_lower == AuthProviderEnum.APPLE.value:
        return AppleOAuthProvider(redis)
    else:
        raise AppException(
            code="INVALID_OAUTH_PROVIDER",
            message=f"지원하지 않는 OAuth 제공자입니다: {provider}",
            status_code=400,
        )


@router.get("/oauth/{provider}", summary="OAuth 로그인 시작")
async def oauth_start(
    provider: str,
    redis: Redis = Depends(get_write_redis),
):
    """
    OAuth 로그인 시작
    
    - 해당 OAuth 제공자의 로그인 페이지로 리다이렉트
    - state 파라미터로 CSRF 방지
    """
    oauth_provider = _get_oauth_provider(provider, redis)
    auth_url, state = await oauth_provider.get_authorization_url()
    
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/oauth/{provider}/callback", summary="OAuth 콜백 (GET)")
async def oauth_callback_get(
    provider: str,
    request: Request,
    response: Response,
    code: str = None,
    state: str = None,
    error: str = None,
    error_description: str = None,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """OAuth 콜백 (GET) - Google, Kakao용"""
    return await _handle_oauth_callback(
        provider=provider,
        request=request,
        response=response,
        code=code,
        state=state,
        error=error,
        error_description=error_description,
        user_data=None,
        db=db,
        redis=redis,
    )


@router.post("/oauth/{provider}/callback", summary="OAuth 콜백 (POST)")
async def oauth_callback_post(
    provider: str,
    request: Request,
    response: Response,
    code: str = Form(None),
    state: str = Form(None),
    error: str = Form(None),
    error_description: str = Form(None),
    user: str = Form(None),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """OAuth 콜백 (POST) - Apple용 (form_post response_mode)"""
    user_data = None
    if user:
        try:
            user_data = json.loads(user)
        except json.JSONDecodeError:
            pass
    
    return await _handle_oauth_callback(
        provider=provider,
        request=request,
        response=response,
        code=code,
        state=state,
        error=error,
        error_description=error_description,
        user_data=user_data,
        db=db,
        redis=redis,
    )


async def _handle_oauth_callback(
    *,
    provider: str,
    request: Request,
    response: Response,
    code: str,
    state: str,
    error: str,
    error_description: str,
    user_data: dict,
    db: AsyncSession,
    redis: Redis,
):
    """OAuth 콜백 공통 처리 로직"""
    
    frontend_url = settings.FRONTEND_URL
    
    # 1. OAuth 에러 처리
    if error:
        error_msg = error_description or error
        redirect_url = f"{frontend_url}/login?error={urlencode({'msg': error_msg})}"
        return RedirectResponse(url=redirect_url, status_code=302)
    
    # 2. code/state 검증
    if not code or not state:
        redirect_url = f"{frontend_url}/login?error=missing_params"
        return RedirectResponse(url=redirect_url, status_code=302)
    
    try:
        # 3. OAuth provider 인스턴스 생성
        oauth_provider = _get_oauth_provider(provider, redis)
        
        # 4. OAuth 인증 처리
        if provider.lower() == AuthProviderEnum.APPLE.value and user_data:
            from auth.oauth.apple import AppleOAuthProvider
            if isinstance(oauth_provider, AppleOAuthProvider):
                user_info = await oauth_provider.authenticate_with_user_data(
                    code=code,
                    state=state,
                    user_data=user_data,
                )
            else:
                user_info = await oauth_provider.authenticate(code, state)
        else:
            user_info = await oauth_provider.authenticate(code, state)
        
        # 5. 로그인/가입 처리 → 토큰 발급
        svc = AuthService(db, redis)
        token_response = await svc.oauth_login(request, response, user_info)
        
        # 6. 프론트엔드로 리다이렉트
        params = {"access_token": token_response.access_token}
        if token_response.refresh_token:
            params["refresh_token"] = token_response.refresh_token
        
        redirect_url = f"{frontend_url}/login/{provider}?{urlencode(params)}"
        return RedirectResponse(url=redirect_url, status_code=302)
        
    except AppException as e:
        redirect_url = f"{frontend_url}/login?error={urlencode({'msg': e.message})}"
        return RedirectResponse(url=redirect_url, status_code=302)
    except ValueError as e:
        redirect_url = f"{frontend_url}/login?error={urlencode({'msg': str(e)})}"
        return RedirectResponse(url=redirect_url, status_code=302)
    except Exception as e:
        redirect_url = f"{frontend_url}/login?error=oauth_failed"
        return RedirectResponse(url=redirect_url, status_code=302)


# ══════════════════════════════════════════════════════════════════════════════
# Driver Mobile — 폰번호 OTP 로그인
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/driver/otp/request",
    response_model=DriverOtpSendResponseSchema,
    summary="기사 모바일 OTP 발송 (폰번호)",
)
async def driver_otp_request(
    body: DriverOtpRequestSchema,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """
    기사 폰번호로 OTP 발송.
    - 데모: SMS 는 콘솔 출력 (로그 + print)
    - 사용자 enumeration 방지: phone 이 DB 에 없어도 성공 응답
    """
    svc = AuthService(db, redis)
    return await svc.request_driver_otp(phone=body.phone)


@router.post(
    "/driver/otp/verify",
    response_model=DriverOtpVerifyResponseSchema,
    summary="기사 모바일 OTP 검증",
)
async def driver_otp_verify(
    body: DriverOtpVerifySchema,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """OTP 검증 성공 시 ok 키 발급 (다음 단계 driver_login 에서 사용)."""
    svc = AuthService(db, redis)
    return await svc.verify_driver_otp(
        phone=body.phone, request_id=body.request_id, code=body.code,
    )


@router.post(
    "/driver/login",
    response_model=TokenResponseSchema,
    summary="기사 모바일 최종 로그인 (verify 통과 후 토큰 발급)",
)
async def driver_login(
    body: DriverLoginSchema,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    """
    polled flow:
      1. /driver/otp/request → SMS 발송
      2. /driver/otp/verify  → ok 키 발급
      3. /driver/login       → user.phone 매칭 + 토큰 발급
    """
    svc = AuthService(db, redis)
    return await svc.driver_login(
        request, response,
        phone=body.phone, request_id=body.request_id,
    )