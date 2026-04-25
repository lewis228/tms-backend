from __future__ import annotations
import json
import time
import bcrypt
import jwt
import secrets
import uuid
from typing import Optional

from jwt import ExpiredSignatureError, InvalidTokenError
from common.email.smtp_sender import send_email_html

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from auth.schemas.request import RegisterUserRequestSchema
from auth.const.providers import AuthProviderEnum
from auth.oauth.base import OAuthUserInfo
from user.model import UserModel
from user.schemas.response import UserResponseSchema
from auth.schemas.response import (
    TokenResponseSchema,
    AccessTokenOnlyResponseSchema,
    RefreshTokenOnlyResponseSchema,
    PasswordCodeSendResponseSchema,
    PasswordCodeVerifyResponseSchema,
    PasswordResetConfirmResponseSchema,
)
from user.repository import UserRepository

from common.const.settings import (
    settings,
    JWT_ALGORITHM, BCRYPT_ROUNDS,
    CLIENT_TYPE_HEADER, DEVICE_KEY_HEADER,
    REFRESH_TOKEN_COOKIE_NAME,
    OTP_TTL, OTP_MAX_TRIES, OTP_OK_TTL,
)
from common.exceptions.base import (
    AppException, UnauthorizedException, NotFoundException, ConflictException
)
from auth.utils.cookies import (
    ensure_browser_id_cookie,
    set_refresh_token_cookie,
    clear_refresh_token_cookie,
)
from auth.utils.time import exp_in, utc_ts
from auth.utils.ids import new_id, new_token_id


class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.user_repository = UserRepository(db)

    # ===== JWT =====
    def verify_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except ExpiredSignatureError:
            raise UnauthorizedException("토큰이 만료되었습니다.")
        except InvalidTokenError:
            raise UnauthorizedException("잘못된 토큰입니다.")

    def sign_token(self, *, sub: int, sid: str, did: str, is_refresh: bool) -> str:
        ttl = settings.REFRESH_TTL if is_refresh else settings.ACCESS_TTL
        payload = {
            "sub": str(sub), "sid": sid, "did": did,
            "type": "refresh" if is_refresh else "access",
            "jti": new_token_id(), "iat": utc_ts(), "exp": exp_in(ttl),
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)

    async def rotate_token(self, refresh_token: str, *, is_refresh: bool) -> tuple[str, Optional[str]]:
        try:
            p = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except ExpiredSignatureError:
            raise UnauthorizedException("리프레시 토큰이 만료되었습니다.")
        except InvalidTokenError:
            raise UnauthorizedException("유효하지 않은 리프레시 토큰입니다.")
        if p.get("type") != "refresh":
            raise UnauthorizedException("Refresh 토큰만 허용됩니다.")
        uid, sid, did = int(p["sub"]), p["sid"], p["did"]
        saved = await self.redis.get(f"refresh:{sid}")
        saved = saved.decode() if isinstance(saved, (bytes, bytearray)) else saved
        if not saved or saved != refresh_token:
            raise UnauthorizedException("리프레시 토큰이 유효하지 않습니다.")
        new_access = self.sign_token(sub=uid, sid=sid, did=did, is_refresh=False)
        new_refresh = None
        if is_refresh:
            new_refresh = self.sign_token(sub=uid, sid=sid, did=did, is_refresh=True)
            pipe = self.redis.pipeline(transaction=True)
            pipe.set(f"refresh:{sid}", new_refresh, ex=settings.REFRESH_TTL)
            pipe.expire(f"sess:{sid}", settings.REFRESH_TTL)
            pipe.expire(f"device:{did}:sid", settings.REFRESH_TTL)
            pipe.expire(f"u:{uid}:sids", settings.REFRESH_TTL)
            await pipe.execute()
        return new_access, new_refresh

    # ===== Email Login =====
    async def authenticate_with_email(self, *, email: str, password: str) -> UserResponseSchema:
        email = email.strip().lower()
        user = await self.user_repository.get_user_for_auth(email)
        if not user:
            existing = await self.user_repository.get_active_user_by_email(email)
            if existing and existing.auth_provider != AuthProviderEnum.EMAIL.value:
                provider_name = AuthProviderEnum(existing.auth_provider).display_name_ko()
                raise AppException(
                    code="USE_OAUTH_LOGIN",
                    message=f"이 이메일은 {provider_name}로 가입되어 있습니다. {provider_name} 로그인을 사용해주세요.",
                    status_code=400,
                )
            raise NotFoundException("일치하는 User가 없습니다.")
        if not bcrypt.checkpw(password.encode("utf-8"), user.password.encode("utf-8")):
            raise UnauthorizedException("비밀번호가 일치하지 않습니다.")
        return UserResponseSchema.model_validate(user)

    # ===== Session Management =====
    async def _create_session(self, request: Request, response: Response, uid: int) -> tuple[str, str, str]:
        client_type = (request.headers.get(CLIENT_TYPE_HEADER) or "web").lower()
        if client_type == "web":
            bid = ensure_browser_id_cookie(request, response)
            did = f"web:{bid}"
        else:
            did = request.headers.get(DEVICE_KEY_HEADER) or f"app:{uuid.uuid4().hex}"
        sid = new_id()
        access = self.sign_token(sub=uid, sid=sid, did=did, is_refresh=False)
        refresh = self.sign_token(sub=uid, sid=sid, did=did, is_refresh=True)
        sess_data = json.dumps({"uid": uid, "did": did})
        pipe = self.redis.pipeline(transaction=True)
        pipe.set(f"sess:{sid}", sess_data, ex=settings.REFRESH_TTL)
        pipe.set(f"refresh:{sid}", refresh, ex=settings.REFRESH_TTL)
        pipe.set(f"device:{did}:sid", sid, ex=settings.REFRESH_TTL)
        pipe.sadd(f"u:{uid}:sids", sid)
        pipe.expire(f"u:{uid}:sids", settings.REFRESH_TTL)
        await pipe.execute()
        return access, refresh, did

    async def login_user(self, request: Request, response: Response, user: UserResponseSchema) -> TokenResponseSchema:
        access, refresh, did = await self._create_session(request, response, user.id)
        client_type = (request.headers.get(CLIENT_TYPE_HEADER) or "web").lower()
        if client_type == "web":
            set_refresh_token_cookie(response, refresh)
            return TokenResponseSchema(access_token=access, refresh_token=None)
        return TokenResponseSchema(access_token=access, refresh_token=refresh)

    async def logout(self, request: Request, response: Response):
        clear_refresh_token_cookie(response)

    async def issue_new_access_from_request(self, request: Request, response: Response) -> AccessTokenOnlyResponseSchema:
        rt = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
        if not rt:
            raise UnauthorizedException("리프레시 토큰이 없습니다.")
        new_access, _ = await self.rotate_token(rt, is_refresh=False)
        return AccessTokenOnlyResponseSchema(access_token=new_access)

    async def rotate_refresh_from_request(self, request: Request, response: Response) -> RefreshTokenOnlyResponseSchema:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise UnauthorizedException("리프레시 토큰이 필요합니다.")
        rt = auth[7:].strip()
        _, new_refresh = await self.rotate_token(rt, is_refresh=True)
        return RefreshTokenOnlyResponseSchema(refresh_token=new_refresh)

    # ===== OAuth =====
    async def authenticate_or_register_oauth(self, user_info: OAuthUserInfo) -> UserResponseSchema:
        user = await self.user_repository.get_user_by_oauth(user_info.provider, user_info.oauth_id)
        if user:
            return UserResponseSchema.model_validate(user)
        if user_info.email:
            conflict = await self.user_repository.check_email_conflict(user_info.email, user_info.provider)
            if conflict:
                raise ConflictException(conflict)
        new_user = UserModel.create_oauth_user(
            provider=user_info.provider, oauth_id=user_info.oauth_id,
            email=user_info.email, name=user_info.name,
        )
        new_user = await self.user_repository.create_user(new_user)
        return UserResponseSchema.model_validate(new_user)

    async def oauth_login(self, request: Request, response: Response, user_info: OAuthUserInfo) -> TokenResponseSchema:
        user = await self.authenticate_or_register_oauth(user_info)
        return await self.login_user(request, response, user)

    # ===== OTP (Password Reset) =====
    async def request_password_reset(self, *, email: str) -> PasswordCodeSendResponseSchema:
        email = email.strip().lower()
        user = await self.user_repository.get_user_by_email(email)
        if not user:
            raise NotFoundException("등록된 이메일이 아닙니다.")
        request_id = new_id()
        code = f"{secrets.randbelow(1000000):06d}"
        key = f"otp:reset:{request_id}"
        data = json.dumps({"email": email, "code": code, "tries": 0})
        await self.redis.set(key, data, ex=OTP_TTL)
        send_email_html(
            to=email,
            subject=f"[{settings.APP_NAME}] 비밀번호 재설정 인증코드",
            html=f"<p>인증코드: <strong>{code}</strong></p>",
            text_fallback=f"인증코드: {code}",
        )
        return PasswordCodeSendResponseSchema(request_id=request_id, expires_in_sec=OTP_TTL)

    async def verify_password_code(self, *, email: str, request_id: str, code: str) -> PasswordCodeVerifyResponseSchema:
        key = f"otp:reset:{request_id}"
        raw = await self.redis.get(key)
        if not raw:
            raise AppException(code="OTP_EXPIRED", message="인증코드가 만료되었습니다.", status_code=400)
        data = json.loads(raw)
        if data["email"] != email.strip().lower():
            raise AppException(code="OTP_EMAIL_MISMATCH", message="이메일이 일치하지 않습니다.", status_code=400)
        if data["tries"] >= OTP_MAX_TRIES:
            await self.redis.delete(key)
            raise AppException(code="OTP_MAX_TRIES", message="최대 시도 횟수를 초과했습니다.", status_code=400)
        if data["code"] != code:
            data["tries"] += 1
            await self.redis.set(key, json.dumps(data), ex=OTP_TTL)
            raise AppException(code="OTP_INVALID", message="인증코드가 일치하지 않습니다.", status_code=400)
        ok_key = f"otp:ok:{request_id}"
        await self.redis.set(ok_key, email, ex=OTP_OK_TTL)
        await self.redis.delete(key)
        return PasswordCodeVerifyResponseSchema(request_id=request_id)

    async def confirm_password_reset(self, *, email: str, request_id: str, new_password: str) -> PasswordResetConfirmResponseSchema:
        ok_key = f"otp:ok:{request_id}"
        stored_email = await self.redis.get(ok_key)
        if not stored_email or stored_email != email.strip().lower():
            raise AppException(code="OTP_NOT_VERIFIED", message="인증이 완료되지 않았습니다.", status_code=400)
        user = await self.user_repository.get_user_by_email(email)
        if not user:
            raise NotFoundException("User")
        pw_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")
        await self.user_repository.update_password_by_id(user.id, pw_hash)
        await self.redis.delete(ok_key)
        return PasswordResetConfirmResponseSchema()

    # ===== OTP (Signup) =====
    async def request_signup_email_code(self, *, email: str) -> PasswordCodeSendResponseSchema:
        email = email.strip().lower()
        if await self.user_repository.exists_email(email):
            raise ConflictException("이미 가입된 이메일입니다.")
        request_id = new_id()
        code = f"{secrets.randbelow(1000000):06d}"
        key = f"otp:signup:{request_id}"
        data = json.dumps({"email": email, "code": code, "tries": 0})
        await self.redis.set(key, data, ex=OTP_TTL)
        send_email_html(
            to=email,
            subject=f"[{settings.APP_NAME}] 회원가입 인증코드",
            html=f"<p>인증코드: <strong>{code}</strong></p>",
            text_fallback=f"인증코드: {code}",
        )
        return PasswordCodeSendResponseSchema(request_id=request_id, expires_in_sec=OTP_TTL)

    async def verify_signup_email_code(self, *, email: str, request_id: str, code: str) -> PasswordCodeVerifyResponseSchema:
        key = f"otp:signup:{request_id}"
        raw = await self.redis.get(key)
        if not raw:
            raise AppException(code="OTP_EXPIRED", message="인증코드가 만료되었습니다.", status_code=400)
        data = json.loads(raw)
        if data["email"] != email.strip().lower():
            raise AppException(code="OTP_EMAIL_MISMATCH", message="이메일이 일치하지 않습니다.", status_code=400)
        if data["tries"] >= OTP_MAX_TRIES:
            await self.redis.delete(key)
            raise AppException(code="OTP_MAX_TRIES", message="최대 시도 횟수를 초과했습니다.", status_code=400)
        if data["code"] != code:
            data["tries"] += 1
            await self.redis.set(key, json.dumps(data), ex=OTP_TTL)
            raise AppException(code="OTP_INVALID", message="인증코드가 일치하지 않습니다.", status_code=400)
        ok_key = f"otp:signup_ok:{request_id}"
        await self.redis.set(ok_key, email, ex=OTP_OK_TTL)
        await self.redis.delete(key)
        return PasswordCodeVerifyResponseSchema(request_id=request_id)

    async def register_and_login_user(self, request: Request, response: Response, body: RegisterUserRequestSchema) -> TokenResponseSchema:
        ok_key = f"otp:signup_ok:{body.request_id}"
        stored_email = await self.redis.get(ok_key)
        if not stored_email or stored_email != body.email.strip().lower():
            raise AppException(code="OTP_NOT_VERIFIED", message="이메일 인증이 완료되지 않았습니다.", status_code=400)
        if await self.user_repository.exists_email(body.email):
            raise ConflictException("이미 가입된 이메일입니다.")
        pw_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")
        new_user = UserModel.create_email_user(email=body.email, password_hash=pw_hash)
        new_user = await self.user_repository.create_user(new_user)
        await self.redis.delete(ok_key)
        user_schema = UserResponseSchema.model_validate(new_user)
        return await self.login_user(request, response, user_schema)
