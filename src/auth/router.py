from __future__ import annotations
import json
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from database.dependencies import get_write_db, get_read_db
from cache.dependencies import get_write_redis, get_read_redis

from auth.service import AuthService
from auth.const.providers import AuthProviderEnum
from auth.oauth.google import GoogleOAuthProvider
from auth.dependencies.basic_token import basic_token
from auth.schemas.request import (
    RegisterUserRequestSchema,
    RegisterEmailCodeSendRequestSchema,
    RegisterEmailCodeVerifyRequestSchema,
    PasswordResetSendCodeRequestSchema,
    PasswordResetVerifyCodeRequestSchema,
    PasswordResetConfirmRequestSchema,
)
from auth.schemas.response import (
    TokenResponseSchema,
    AccessTokenOnlyResponseSchema,
    RefreshTokenOnlyResponseSchema,
    PasswordCodeSendResponseSchema,
    PasswordCodeVerifyResponseSchema,
    PasswordResetConfirmResponseSchema,
)
from user.schemas.response import UserResponseSchema
from common.const.settings import settings
from common.exceptions.base import AppException

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponseSchema)
async def login(
    request: Request, response: Response,
    _user: UserResponseSchema = Depends(basic_token),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    auth = AuthService(db, redis)
    user: UserResponseSchema = request.state.user
    return await auth.login_user(request, response, user)


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    svc = AuthService(db, redis)
    await svc.logout(request, response)


@router.post("/token/access", response_model=AccessTokenOnlyResponseSchema)
async def issue_access_token(
    request: Request, response: Response,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_read_redis),
):
    svc = AuthService(db, redis)
    return await svc.issue_new_access_from_request(request, response)


@router.post("/token/refresh", response_model=RefreshTokenOnlyResponseSchema)
async def rotate_refresh_token(
    request: Request, response: Response,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    svc = AuthService(db, redis)
    return await svc.rotate_refresh_from_request(request, response)


@router.post("/register/email/request", response_model=PasswordCodeSendResponseSchema)
async def send_signup_email_code(
    body: RegisterEmailCodeSendRequestSchema,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_write_redis),
):
    svc = AuthService(db, redis)
    return await svc.request_signup_email_code(email=body.email)


@router.post("/register/email/verify", response_model=PasswordCodeVerifyResponseSchema)
async def verify_signup_email_code(
    body: RegisterEmailCodeVerifyRequestSchema,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_write_redis),
):
    svc = AuthService(db, redis)
    return await svc.verify_signup_email_code(email=body.email, request_id=body.request_id, code=body.code)


@router.post("/register", response_model=TokenResponseSchema)
async def register_user(
    request: Request, response: Response,
    body: RegisterUserRequestSchema,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    svc = AuthService(db, redis)
    return await svc.register_and_login_user(request, response, body)


@router.post("/password/reset/request", response_model=PasswordCodeSendResponseSchema)
async def send_password_reset_code(
    body: PasswordResetSendCodeRequestSchema,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_write_redis),
):
    svc = AuthService(db, redis)
    return await svc.request_password_reset(email=body.email)


@router.post("/password/reset/verify", response_model=PasswordCodeVerifyResponseSchema)
async def verify_password_reset_code(
    body: PasswordResetVerifyCodeRequestSchema,
    db: AsyncSession = Depends(get_read_db),
    redis: Redis = Depends(get_write_redis),
):
    svc = AuthService(db, redis)
    return await svc.verify_password_code(email=body.email, request_id=body.request_id, code=body.code)


@router.post("/password/reset/confirm", response_model=PasswordResetConfirmResponseSchema)
async def confirm_password_reset(
    body: PasswordResetConfirmRequestSchema,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    svc = AuthService(db, redis)
    return await svc.confirm_password_reset(email=body.email, request_id=body.request_id, new_password=body.new_password)


# ===== OAuth =====
def _get_oauth_provider(provider: str, redis: Redis):
    provider_lower = provider.lower()
    if provider_lower == AuthProviderEnum.GOOGLE.value:
        return GoogleOAuthProvider(redis)
    # Add more providers here (Kakao, Apple, etc.)
    raise AppException(code="INVALID_OAUTH_PROVIDER", message=f"지원하지 않는 OAuth 제공자입니다: {provider}", status_code=400)


@router.get("/oauth/{provider}")
async def oauth_start(provider: str, redis: Redis = Depends(get_write_redis)):
    oauth_provider = _get_oauth_provider(provider, redis)
    auth_url, state = await oauth_provider.get_authorization_url()
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/oauth/{provider}/callback")
async def oauth_callback_get(
    provider: str, request: Request, response: Response,
    code: str = None, state: str = None,
    error: str = None, error_description: str = None,
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
):
    return await _handle_oauth_callback(
        provider=provider, request=request, response=response,
        code=code, state=state, error=error,
        error_description=error_description, db=db, redis=redis,
    )


async def _handle_oauth_callback(*, provider, request, response, code, state, error, error_description, db, redis):
    frontend_url = settings.FRONTEND_URL
    if error:
        return RedirectResponse(url=f"{frontend_url}/login?error={urlencode({'msg': error_description or error})}", status_code=302)
    if not code or not state:
        return RedirectResponse(url=f"{frontend_url}/login?error=missing_params", status_code=302)
    try:
        oauth_provider = _get_oauth_provider(provider, redis)
        user_info = await oauth_provider.authenticate(code, state)
        svc = AuthService(db, redis)
        token_response = await svc.oauth_login(request, response, user_info)
        params = {"access_token": token_response.access_token}
        if token_response.refresh_token:
            params["refresh_token"] = token_response.refresh_token
        return RedirectResponse(url=f"{frontend_url}/oauth/callback?{urlencode(params)}", status_code=302)
    except Exception:
        return RedirectResponse(url=f"{frontend_url}/login?error=oauth_failed", status_code=302)
