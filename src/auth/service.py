# src/auth/service.py
from __future__ import annotations
import json
import time
import bcrypt
import jwt
import secrets
import uuid
from typing import Optional, Iterable, Callable

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

from common.const.settings import settings
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
    """인증/세션/토큰, 이메일 OTP, 회원가입/로그인/로그아웃, OAuth를 담당하는 도메인 서비스."""

    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.user_repository = UserRepository(db)

    # ══════════════════════════════════════════════════════════════════════════
    # JWT
    # ══════════════════════════════════════════════════════════════════════════
    def verify_token(self, token: str) -> dict:
        """JWT 검증 → payload 반환. 실패 시 UnauthorizedException."""
        try:
            return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise UnauthorizedException("토큰이 만료되었습니다.")
        except InvalidTokenError:
            raise UnauthorizedException("잘못된 토큰입니다.")

    def sign_token(self, *, sub: int, sid: str, did: str, is_refresh: bool, role: str | None = None) -> str:
        """access/refresh 토큰 발급 공통 메서드."""
        ttl = settings.REFRESH_TTL if is_refresh else settings.ACCESS_TTL
        payload: dict = {
            "sub": str(sub),
            "sid": sid,
            "did": did,
            "type": "refresh" if is_refresh else "access",
            "jti": new_token_id(),
            "iat": utc_ts(),
            "exp": exp_in(ttl),
        }
        # WS / 미들웨어가 토큰만으로 role 판정 가능하게 access 토큰엔 role 포함.
        if role and not is_refresh:
            payload["role"] = role
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

    async def rotate_token(self, refresh_token: str, *, is_refresh: bool) -> tuple[str, Optional[str]]:
        """refresh 토큰으로 새로운 access(및 선택적으로 refresh) 발급."""
        try:
            p = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise UnauthorizedException("리프레시 토큰이 만료되었습니다.")
        except InvalidTokenError:
            raise UnauthorizedException("유효하지 않은 리프레시 토큰입니다.")

        if p.get("type") != "refresh":
            raise UnauthorizedException("Refresh 토큰만 허용됩니다.")

        uid = int(p["sub"])
        sid = p["sid"]
        did = p["did"]

        saved = await self.redis.get(f"refresh:{sid}")
        saved = saved.decode() if isinstance(saved, (bytes, bytearray)) else saved
        if not saved or saved != refresh_token:
            raise UnauthorizedException("리프레시 토큰이 유효하지 않습니다.")

        # rotate 시 user role 을 다시 조회해 새 access 토큰에 박는다 (WS 가 토큰만으로 판정).
        user = await self.user_repository.get_user_by_id(uid)
        role_value = (
            getattr(getattr(user, "role", None), "value", None)
            if user is not None else None
        )
        new_access = self.sign_token(
            sub=uid, sid=sid, did=did, is_refresh=False, role=role_value,
        )

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

    # ══════════════════════════════════════════════════════════════════════════
    # 이메일 로그인 (기존)
    # ══════════════════════════════════════════════════════════════════════════
    async def authenticate_with_email(self, *, email: str, password: str) -> UserResponseSchema:
        """
        이메일/비밀번호 인증
        - repo.get_user_for_auth()로 auth_provider='email'인 사용자만 조회
        """
        email = email.strip().lower()
        user = await self.user_repository.get_user_for_auth(email)
        if not user:
            # 이메일이 없거나 OAuth 사용자인 경우
            # OAuth 사용자인지 체크해서 더 정확한 메시지 제공
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

    # ══════════════════════════════════════════════════════════════════════════
    # OAuth 로그인/가입
    # ══════════════════════════════════════════════════════════════════════════
    async def authenticate_or_register_oauth(
        self,
        user_info: OAuthUserInfo,
    ) -> UserResponseSchema:
        """
        OAuth 사용자 인증 또는 신규 가입.
        
        1. oauth_id로 기존 사용자 조회
        2. 있으면 → 로그인
        3. 없으면 → 이메일 충돌 검사 후 신규 가입 + 프로필 이미지 저장
        
        Args:
            user_info: OAuth 제공자로부터 받은 사용자 정보
            
        Returns:
            UserResponseSchema
        """
        provider = user_info.provider
        oauth_id = user_info.oauth_id
        email = user_info.email
        
        # 1. 기존 OAuth 사용자 조회
        existing_user = await self.user_repository.get_user_by_oauth(provider, oauth_id)
        if existing_user:
            return UserResponseSchema.model_validate(existing_user)
        
        # 2. 이메일 충돌 검사 (같은 이메일로 다른 방식 가입 여부)
        if email:
            conflict_msg = await self.user_repository.check_email_conflict(email, provider)
            if conflict_msg:
                raise ConflictException(conflict_msg)
        
        # 3. 신규 OAuth 사용자 생성
        new_user = UserModel.create_oauth_user(
            provider=provider,
            oauth_id=oauth_id,
            email=email,
            name=user_info.name,
        )
        created = await self.user_repository.create_user(new_user)
        
        #  4. 프로필 이미지 저장 (신규 가입 시에만, 있는 경우만)
        #    - Google/Kakao/Apple 모두 동일 로직: 이미지 URL 있으면 저장, 없으면 skip
        #    - 실패해도 회원가입에는 영향 없음 (나중에 직접 업로드 가능)
        if user_info.profile_image:
            from file.service import FileService
            file_svc = FileService(self.db)
            await file_svc.save_oauth_profile_image(
                user_id=created.id,
                image_url=user_info.profile_image,
            )
        
        return UserResponseSchema.model_validate(created)

    async def oauth_login(
        self,
        request: Request,
        response: Response,
        user_info: OAuthUserInfo,
    ) -> TokenResponseSchema:
        """
        OAuth 전체 플로우: 인증/가입 → 로그인 → 토큰 발급
        """
        # 1. 인증 또는 가입
        user = await self.authenticate_or_register_oauth(user_info)
        
        # 2. 세션 생성 및 토큰 발급
        return await self.login_user(request, response, user)

    # ══════════════════════════════════════════════════════════════════════════
    # 로그인 (공통)
    # ══════════════════════════════════════════════════════════════════════════
    async def login_user(self, request: Request, response: Response, user: UserResponseSchema) -> TokenResponseSchema:
        """
        로그인 후 세션/토큰 발급 처리.
        - 기기/브라우저 식별자에 따라 세션 고유화
        - Redis: sess, refresh, device→sid, u:{uid}:sids
        - 웹은 refresh를 HttpOnly 쿠키로 내려주고, 바디는 access만 반환
        """
        uid = int(user.id)
        client_type = (request.headers.get(settings.CLIENT_TYPE_HEADER) or "").lower()

        if client_type == "web":
            browser_id = ensure_browser_id_cookie(request, response)
            did = f"web:{browser_id}"
        else:
            did = request.headers.get(settings.DEVICE_KEY_HEADER)
            if not did:
                raise UnauthorizedException(f"{settings.DEVICE_KEY_HEADER} header가 없습니다.")

        dev_map_key = f"device:{did}:sid"

        # 이전 디바이스 매핑이 있으면 깔끔히 종료/정리
        prev_sid_raw = await self.redis.get(dev_map_key)
        prev_sid = prev_sid_raw.decode() if isinstance(prev_sid_raw, (bytes, bytearray)) else prev_sid_raw
        if prev_sid:
            prev_sess_raw = await self.redis.get(f"sess:{prev_sid}")
            if prev_sess_raw:
                try:
                    prev_sess = json.loads(prev_sess_raw.decode())
                    prev_jti = prev_sess.get("jti")
                    prev_exp = prev_sess.get("exp")
                    if prev_jti and prev_exp:
                        ttl = max(0, int(prev_exp) - utc_ts())
                        if ttl > 0:
                            await self.redis.set(f"bl:a:{prev_jti}", 1, ex=ttl)
                except Exception:
                    pass
            pipe = self.redis.pipeline(transaction=True)
            pipe.delete(f"sess:{prev_sid}")
            pipe.delete(f"refresh:{prev_sid}")
            pipe.srem(f"u:{uid}:sids", prev_sid)
            await pipe.execute()

        # 새 세션 발급
        sid = new_id()

        access_jti = new_token_id()
        access_exp = exp_in(settings.ACCESS_TTL)
        role_str = getattr(getattr(user, "role", None), "value", str(getattr(user, "role", "")))
        access_payload = {
            "sub": str(uid), "sid": sid, "did": did,
            "type": "access", "jti": access_jti,
            "iat": utc_ts(), "exp": access_exp,
            # WS / 미들웨어가 토큰만으로 role 판정할 수 있게 노출.
            "role": role_str,
        }

        # DRIVER 는 1:1 team 관계 (한 운전기사 = 한 회사) → 토큰에 team_id claim 박아
        # 이후 모든 요청에서 DB/Redis 0 으로 team_id 추출 (X-Team-Id 헤더 불필요).
        # Dispatcher / Admin 은 N:M 가능 → 기존대로 X-Team-Id 헤더 사용.
        if role_str == "DRIVER":
            # 지역 import — auth → driver 의존 방향 침범 최소화 (예외적 cross-domain).
            from driver.model import DriverModel
            from sqlalchemy import select
            driver_team_id = await self.db.scalar(
                select(DriverModel.team_id)
                .where(
                    DriverModel.user_id == uid,
                    DriverModel.is_active.is_(True),
                )
                .limit(1)
            )
            if driver_team_id is not None:
                access_payload["team_id"] = int(driver_team_id)

        access = jwt.encode(access_payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
        refresh = self.sign_token(sub=uid, sid=sid, did=did, is_refresh=True)

        # Redis 등록
        sess_obj = {"uid": uid, "did": did, "status": "active", "jti": access_jti, "exp": access_exp}
        pipe = self.redis.pipeline(transaction=True)
        pipe.set(f"sess:{sid}", json.dumps(sess_obj), ex=settings.REFRESH_TTL)
        pipe.set(f"refresh:{sid}", refresh, ex=settings.REFRESH_TTL)
        pipe.set(dev_map_key, sid, ex=settings.REFRESH_TTL)
        pipe.sadd(f"u:{uid}:sids", sid)
        pipe.expire(f"u:{uid}:sids", settings.REFRESH_TTL)
        await pipe.execute()

        if client_type == "web":
            set_refresh_token_cookie(response, refresh)
            return TokenResponseSchema(access_token=access, refresh_token=None)  #  snake_case
        else:
            return TokenResponseSchema(access_token=access, refresh_token=refresh)  #  snake_case

    # ══════════════════════════════════════════════════════════════════════════
    # 로그아웃
    # ══════════════════════════════════════════════════════════════════════════
    async def logout(self, request: Request, response: Response) -> None:
        """가능하면 access, 대안으로 refresh 기반으로 세션/쿠키 정리."""
        def _bearer_or_none(h: Optional[str]) -> Optional[str]:
            if not h:
                return None
            try:
                typ, val = h.split(" ", 1)
                return val if typ == "Bearer" and val else None
            except Exception:
                return None

        authz = request.headers.get("Authorization")
        access_bearer = _bearer_or_none(authz)

        # 1) access 유효 → 정확 종료
        if access_bearer:
            try:
                p = self.verify_token(access_bearer)
                uid = int(p["sub"])
                sid = p["sid"]
                did = p["did"]
                jti = p.get("jti")
                exp = int(p["exp"])

                pipe = self.redis.pipeline(transaction=True)
                pipe.delete(f"sess:{sid}")
                pipe.delete(f"refresh:{sid}")
                pipe.delete(f"device:{did}:sid")
                pipe.srem(f"u:{uid}:sids", sid)
                await pipe.execute()

                if jti:
                    ttl = max(0, exp - utc_ts())
                    if ttl > 0:
                        await self.redis.set(f"bl:a:{jti}", 1, ex=ttl)

                clear_refresh_token_cookie(response)
                return
            except Exception:
                pass

        # 2) refresh 기반 (웹 우선)
        client_type = (request.headers.get(settings.CLIENT_TYPE_HEADER) or "").lower()

        if client_type == "web":
            refresh_cookie = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
            if refresh_cookie:
                try:
                    p = self.verify_token(refresh_cookie)
                    if p.get("type") != "refresh":
                        raise UnauthorizedException("Refresh 토큰이 아닙니다.")
                    uid = int(p["sub"])
                    sid = p["sid"]
                    did = p["did"]

                    pipe = self.redis.pipeline(transaction=True)
                    pipe.delete(f"sess:{sid}")
                    pipe.delete(f"refresh:{sid}")
                    pipe.delete(f"device:{did}:sid")
                    pipe.srem(f"u:{uid}:sids", sid)
                    await pipe.execute()
                except Exception:
                    pass

            clear_refresh_token_cookie(response)
            return

        refresh_bearer = _bearer_or_none(authz)
        if refresh_bearer:
            try:
                p = self.verify_token(refresh_bearer)
                if p.get("type") != "refresh":
                    raise UnauthorizedException("Refresh 토큰이 아닙니다.")
                uid = int(p["sub"])
                sid = p["sid"]
                did = p["did"]

                pipe = self.redis.pipeline(transaction=True)
                pipe.delete(f"sess:{sid}")
                pipe.delete(f"refresh:{sid}")
                pipe.delete(f"device:{did}:sid")
                pipe.srem(f"u:{uid}:sids", sid)
                await pipe.execute()
            except Exception:
                pass

        clear_refresh_token_cookie(response)

    # ══════════════════════════════════════════════════════════════════════════
    # OTP 공통 헬퍼
    # ══════════════════════════════════════════════════════════════════════════
    def _otp_key(self, email: str) -> str: return f"pwreset:{email.lower()}"
    def _try_key(self, email: str) -> str: return f"pwreset_try:{email.lower()}"
    def _send_key(self, email: str) -> str: return f"pwreset_send:{email.lower()}"

    def _reg_otp_key(self, email: str) -> str: return f"regotp:{email.lower()}"
    def _reg_try_key(self, email: str) -> str: return f"regotp_try:{email.lower()}"
    def _reg_send_key(self, email: str) -> str: return f"regotp_send:{email.lower()}"
    def _reg_ok_key(self, email: str) -> str:  return f"regotp_ok:{email.lower()}"

    async def _verify_otp_common(
        self,
        *,
        email: str,
        request_id: str,
        code: str,
        otp_key_builder: Callable[[str], str],
        try_key_builder: Callable[[str], str],
        ok_key_builder: Optional[Callable[[str], str]] = None,
        ok_ttl_seconds: Optional[int] = None,
    ) -> None:
        """OTP 검증 공통 로직."""
        email_l = email.strip().lower()
        otp_key = otp_key_builder(email_l)
        try_key = try_key_builder(email_l)

        raw = await self.redis.get(otp_key)
        if not raw:
            raise AppException(
                code="OTP_NOT_FOUND",
                message="요청 내역이 없습니다. 다시 시도해 주세요.",
                status_code=404,
                detail={"attempts_left": settings.OTP_MAX_TRIES, "seconds_left": 0},
            )
        raw = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw

        try:
            saved_code, saved_req, exp = raw.split("|")
            exp = int(exp)
        except Exception:
            raise AppException(code="OTP_CORRUPTED", message="잘못된 상태입니다. 다시 시도해 주세요.", status_code=400)

        now = int(time.time())
        if request_id != saved_req:
            raise AppException(code="OTP_REQUEST_MISMATCH", message="이전 코드이거나 잘못된 요청입니다.", status_code=400)
        if now > (exp + settings.OTP_GRACE_SEC):
            raise AppException(
                code="OTP_EXPIRED",
                message="코드가 만료되었습니다.",
                status_code=400,
                detail={"attempts_left": settings.OTP_MAX_TRIES, "seconds_left": 0},
            )

        if code != saved_code:
            n = await self.redis.incr(try_key)
            left_ttl = max(1, (exp + settings.OTP_GRACE_SEC) - now)
            await self.redis.expire(try_key, left_ttl)

            attempts_left = max(0, settings.OTP_MAX_TRIES - int(n))

            if int(n) >= settings.OTP_MAX_TRIES:
                pipe = self.redis.pipeline(transaction=True)
                pipe.delete(otp_key)
                pipe.delete(try_key)
                await pipe.execute()
                raise AppException(
                    code="OTP_TOO_MANY_TRIES",
                    message="시도 횟수가 초과되었습니다. 인증 코드를 재발송해 주세요.",
                    status_code=429,
                    detail={"attempts_left": 0, "seconds_left": 0},
                )

            raise AppException(
                code="OTP_NOT_MATCH",
                message="코드가 일치하지 않습니다.",
                status_code=400,
                detail={"attempts_left": attempts_left, "seconds_left": left_ttl},
            )

        if ok_key_builder is not None:
            ok_key = ok_key_builder(email_l)
            ttl = int(ok_ttl_seconds if ok_ttl_seconds is not None else settings.OTP_TTL)
            await self.redis.set(ok_key, request_id, ex=ttl + settings.OTP_GRACE_SEC)

    # ══════════════════════════════════════════════════════════════════════════
    # OTP (비밀번호 재설정)
    # ══════════════════════════════════════════════════════════════════════════
    async def _increase_send_and_check_limit(self, email: str) -> None:
        """비밀번호 재설정 메일 발송 롤링 제한"""
        k = self._send_key(email)
        n = await self.redis.incr(k)
        if n == 1:
            await self.redis.expire(k, int(settings.OTP_BLOCK_SEC))
        if n > settings.OTP_SEND_LIMIT:
            ttl = await self.redis.ttl(k)
            ttl = int(settings.OTP_BLOCK_SEC) if (ttl is None or ttl < 0) else int(ttl)
            await self.redis.expire(k, ttl)
            raise AppException(
                code="TOO_MANY_REQUESTS",
                message="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                status_code=429,
                detail={"send_limit": settings.OTP_SEND_LIMIT, "seconds_left": max(0, ttl)},
            )

    def _render_otp_email_html(self, *, code: str, request_id: str, minutes: int) -> str:
        app = settings.APP_NAME
        logo = settings.BRAND_LOGO_URL
        color = settings.BRAND_PRIMARY_COLOR
        address = settings.COMPANY_ADDRESS
        frontend = settings.FRONTEND_URL
        pre = f"{minutes}분 내에 인증 코드를 입력해 주세요."
        return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{app} 인증 코드</title><span style="display:none!important">{pre}</span>
</head><body style="margin:0;padding:0;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Apple SD Gothic Neo','Noto Sans KR',Helvetica,Arial,sans-serif">
<table align="center" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto">
  <!-- 로고 -->
  <tr><td style="padding:40px 24px 24px;text-align:left">
    <a href="{frontend}" style="text-decoration:none"><img src="{logo}" alt="{app}" style="height:56px;border:0"/></a>
  </td></tr>

  <!-- 메인 콘텐츠 -->
  <tr><td style="padding:0 24px;text-align:left">
    <h1 style="margin:0 0 12px;font-size:22px;font-weight:700;color:#111827;line-height:1.4">{app} 비밀번호 재설정</h1>
    <p style="margin:0 0 24px;font-size:15px;color:#4b5563;line-height:1.6">아래 코드를 <b>{minutes}분</b> 내에 입력해 주세요.</p>
    <div style="margin:0 0 8px;padding:16px 24px;border:1px solid #c7d2fe;background:#eef2ff;display:inline-block;border-radius:10px">
      <span style="font-size:30px;font-weight:800;color:{color};letter-spacing:6px">{code}</span>
    </div>
  </td></tr>

  <!-- 하단 -->
  <tr><td style="padding:40px 24px 0">
    <table width="100%" cellpadding="0" cellspacing="0"><tr><td style="border-top:1px solid #e5e7eb"></td></tr></table>
  </td></tr>
  <tr><td style="padding:20px 24px 40px;text-align:left">
    <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6">{address}</p>
  </td></tr>
</table>
</body></html>"""

    async def request_password_reset(self, *, email: str) -> PasswordCodeSendResponseSchema:
        """비밀번호 재설정: 이메일 OTP 전송."""
        user = await self.user_repository.get_user_by_email(email)
        if not user:
            raise NotFoundException("이메일이 존재하지 않습니다.")
        
        #  OAuth 사용자는 비밀번호 재설정 불가
        if user.auth_provider != AuthProviderEnum.EMAIL.value:
            provider_name = AuthProviderEnum(user.auth_provider).display_name_ko()
            raise AppException(
                code="OAUTH_NO_PASSWORD",
                message=f"이 계정은 {provider_name}로 가입되어 비밀번호가 없습니다. {provider_name} 로그인을 사용해주세요.",
                status_code=400,
            )

        await self._increase_send_and_check_limit(email)

        now = int(time.time())
        code = f"{secrets.randbelow(10**6):06d}"
        request_id = uuid.uuid4().hex
        expire_epoch = now + settings.OTP_TTL
        value = f"{code}|{request_id}|{expire_epoch}"

        pipe = self.redis.pipeline(transaction=True)
        pipe.set(self._otp_key(email), value, ex=settings.OTP_TTL + settings.OTP_GRACE_SEC)
        pipe.delete(self._try_key(email))
        await pipe.execute()

        minutes = max(1, settings.OTP_TTL // 60)
        subject = f"[{settings.APP_NAME}] 비밀번호 재설정 인증 코드"
        text = f"{settings.APP_NAME}\n\n인증 코드: {code}\n요청ID: {request_id}\n{minutes}분 이내에 입력해 주세요."
        html = self._render_otp_email_html(code=code, request_id=request_id, minutes=minutes)
        send_email_html(to=email, subject=subject, html=html, text_fallback=text)

        return PasswordCodeSendResponseSchema(request_id=request_id, expires_in_sec=settings.OTP_TTL)  #  snake_case

    async def verify_password_code(self, *, email: str, request_id: str, code: str) -> PasswordCodeVerifyResponseSchema:
        """비밀번호 재설정: 이메일 OTP 검증."""
        await self._verify_otp_common(
            email=email,
            request_id=request_id,
            code=code,
            otp_key_builder=self._otp_key,
            try_key_builder=self._try_key,
            ok_key_builder=None,
            ok_ttl_seconds=None,
        )
        return PasswordCodeVerifyResponseSchema(request_id=request_id)  #  snake_case

    async def confirm_password_reset(self, *, email: str, request_id: str, new_password: str) -> PasswordResetConfirmResponseSchema:
        """비밀번호 재설정: 최종 비밀번호 변경."""
        raw = await self.redis.get(self._otp_key(email))
        if not raw:
            raise AppException(code="OTP_EXPIRED", message="인증이 만료되었습니다. 처음부터 다시 시도해 주세요.", status_code=400)
        raw = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw

        try:
            _saved_code, saved_req, exp = raw.split("|")
            exp = int(exp)
        except Exception:
            raise AppException(code="OTP_CORRUPTED", message="잘못된 상태입니다.", status_code=400)

        now = int(time.time())
        if request_id != saved_req or now > (exp + settings.OTP_GRACE_SEC):
            raise AppException(code="OTP_EXPIRED", message="인증이 만료되었거나 무효합니다.", status_code=400)

        user = await self.user_repository.get_user_by_email(email)
        if not user:
            raise NotFoundException("사용자를 찾을 수 없습니다.")

        if len(new_password) < 8:
            raise AppException(code="WEAK_PASSWORD", message="비밀번호는 8자 이상이어야 합니다.", status_code=400)

        pw_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode()
        await self.user_repository.update_password_by_id(user.id, pw_hash)

        await self._invalidate_all_user_sessions(user.id)

        await self.redis.delete(self._otp_key(email))
        await self.redis.delete(self._try_key(email))

        return PasswordResetConfirmResponseSchema(ok=True)

    async def _invalidate_all_user_sessions(self, uid: int) -> None:
        """사용자의 모든 세션을 무효화."""
        key = f"u:{uid}:sids"
        members: Iterable[bytes] | None = await self.redis.smembers(key)
        if not members:
            return
        pipe = self.redis.pipeline(transaction=True)
        for sid_b in members:
            sid = sid_b.decode() if isinstance(sid_b, (bytes, bytearray)) else sid_b
            pipe.delete(f"sess:{sid}")
            pipe.delete(f"refresh:{sid}")
        pipe.delete(key)
        await pipe.execute()

    # ══════════════════════════════════════════════════════════════════════════
    # 회원가입 (이메일 OTP)
    # ══════════════════════════════════════════════════════════════════════════
    async def _increase_reg_send_and_check_limit(self, email: str):
        """회원가입용 이메일 OTP 전송 제한."""
        k = self._reg_send_key(email)
        n = await self.redis.incr(k)
        if n == 1:
            await self.redis.expire(k, int(settings.OTP_BLOCK_SEC))
        if n > settings.OTP_SEND_LIMIT:
            ttl = await self.redis.ttl(k)
            ttl = int(settings.OTP_BLOCK_SEC) if (ttl is None or ttl < 0) else int(ttl)
            await self.redis.expire(k, ttl)
            raise AppException(
                code="TOO_MANY_REQUESTS",
                message="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                status_code=429,
                detail={"send_limit": settings.OTP_SEND_LIMIT, "seconds_left": max(0, ttl)},
            )

    def _render_signup_email_html(self, *, code: str, request_id: str, minutes: int) -> str:
        app = settings.APP_NAME
        logo = settings.BRAND_LOGO_URL
        color = settings.BRAND_PRIMARY_COLOR
        address = settings.COMPANY_ADDRESS
        frontend = settings.FRONTEND_URL
        pre = f"{minutes}분 내에 인증 코드를 입력해 주세요."
        return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{app} 회원가입 인증 코드</title><span style="display:none!important">{pre}</span>
</head><body style="margin:0;padding:0;background:#ffffff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Apple SD Gothic Neo','Noto Sans KR',Helvetica,Arial,sans-serif">
<table align="center" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto">
  <!-- 로고 -->
  <tr><td style="padding:40px 24px 24px;text-align:left">
    <a href="{frontend}" style="text-decoration:none"><img src="{logo}" alt="{app}" style="height:56px;border:0"/></a>
  </td></tr>

  <!-- 메인 콘텐츠 -->
  <tr><td style="padding:0 24px;text-align:left">
    <h1 style="margin:0 0 12px;font-size:22px;font-weight:700;color:#111827;line-height:1.4">{app} 회원가입 인증</h1>
    <p style="margin:0 0 24px;font-size:15px;color:#4b5563;line-height:1.6">아래 코드를 <b>{minutes}분</b> 내에 입력해 주세요.</p>
    <div style="margin:0 0 8px;padding:16px 24px;border:1px solid #c7d2fe;background:#eef2ff;display:inline-block;border-radius:10px">
      <span style="font-size:30px;font-weight:800;color:{color};letter-spacing:6px">{code}</span>
    </div>
  </td></tr>

  <!-- 하단 -->
  <tr><td style="padding:40px 24px 0">
    <table width="100%" cellpadding="0" cellspacing="0"><tr><td style="border-top:1px solid #e5e7eb"></td></tr></table>
  </td></tr>
  <tr><td style="padding:20px 24px 40px;text-align:left">
    <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6">{address}</p>
  </td></tr>
</table>
</body></html>"""

    async def request_signup_email_code(self, *, email: str) -> PasswordCodeSendResponseSchema:
        """회원가입: 이메일 OTP 코드 전송."""
        email = email.strip().lower()
        
        #  이메일 중복 체크 (provider 상관없이)
        existing = await self.user_repository.get_active_user_by_email(email)
        if existing:
            provider_name = AuthProviderEnum(existing.auth_provider).display_name_ko()
            raise ConflictException("이미 가입된 이메일입니다.")

        await self._increase_reg_send_and_check_limit(email)

        now = int(time.time())
        code = f"{secrets.randbelow(10**6):06d}"
        request_id = uuid.uuid4().hex
        expire_epoch = now + settings.OTP_TTL
        value = f"{code}|{request_id}|{expire_epoch}"

        pipe = self.redis.pipeline(transaction=True)
        pipe.set(self._reg_otp_key(email), value, ex=settings.OTP_TTL + settings.OTP_GRACE_SEC)
        pipe.delete(self._reg_try_key(email))
        await pipe.execute()

        minutes = max(1, settings.OTP_TTL // 60)
        subject = f"[{settings.APP_NAME}] 회원가입 인증 코드"
        text = f"{settings.APP_NAME}\n\n인증 코드: {code}\n요청ID: {request_id}\n{minutes}분 이내에 입력해 주세요."
        html = self._render_signup_email_html(code=code, request_id=request_id, minutes=minutes)
        send_email_html(to=email, subject=subject, html=html, text_fallback=text)

        return PasswordCodeSendResponseSchema(request_id=request_id, expires_in_sec=settings.OTP_TTL)  #  snake_case

    async def verify_signup_email_code(self, *, email: str, request_id: str, code: str) -> PasswordCodeVerifyResponseSchema:
        """회원가입: 이메일 OTP 코드 검증."""
        await self._verify_otp_common(
            email=email,
            request_id=request_id,
            code=code,
            otp_key_builder=self._reg_otp_key,
            try_key_builder=self._reg_try_key,
            ok_key_builder=self._reg_ok_key,
            ok_ttl_seconds=int(getattr(settings, "OTP_OK_TTL", settings.OTP_TTL)),
        )
        return PasswordCodeVerifyResponseSchema(request_id=request_id)  #  snake_case

    async def ensure_signup_email_verified(self, *, email: str, request_id: str) -> None:
        """최종 가입 직전, 이메일 검증 OK 키 확인."""
        email = email.strip().lower()
        ok = await self.redis.get(self._reg_ok_key(email))
        ok = ok.decode() if isinstance(ok, (bytes, bytearray)) else ok
        if not ok or ok != request_id:
            raise AppException(code="SIGNUP_EMAIL_NOT_VERIFIED", message="이메일 인증이 만료되었거나 무효합니다.", status_code=400)

        pipe = self.redis.pipeline(transaction=True)
        pipe.delete(self._reg_ok_key(email))
        pipe.delete(self._reg_otp_key(email))
        pipe.delete(self._reg_try_key(email))
        await pipe.execute()

    async def register_and_login_user(
        self,
        request: Request,
        response: Response,
        user_data: RegisterUserRequestSchema,
    ) -> TokenResponseSchema:
        """회원가입 + 자동 로그인"""
        await self.ensure_signup_email_verified(
            email=user_data.email, request_id=user_data.request_id  #  snake_case
        )

        new_user = await self.register_user(user_data=user_data)

        try:
            return await self.login_user(request, response, new_user)
        except Exception as e:
            await self.user_repository.hard_delete_user_by_id(new_user.id)
            raise e

    async def register_user(
        self,
        user_data: Optional[RegisterUserRequestSchema] = None,
        *,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ) -> UserResponseSchema:
        """이메일 회원가입 처리."""
        if user_data is not None:
            email = user_data.email.strip().lower()
            password = user_data.password
        else:
            email = (email or "").strip().lower()
            password = password or ""

        if not email or not password:
            raise AppException(code="INVALID_INPUT", message="이메일/비밀번호가 누락되었습니다.", status_code=400)

        #  이메일 충돌 검사 (provider 상관없이)
        existing = await self.user_repository.get_active_user_by_email(email)
        if existing:
            provider_name = AuthProviderEnum(existing.auth_provider).display_name_ko()
            raise ConflictException("이미 가입된 이메일입니다.")

        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()

        new_user = UserModel.create_email_user(
            email=email,
            password_hash=pw_hash,
        )
        created = await self.user_repository.create_user(new_user)
        return UserResponseSchema.model_validate(created)

    # ══════════════════════════════════════════════════════════════════════════
    # 토큰 재발급
    # ══════════════════════════════════════════════════════════════════════════
    async def issue_new_access_from_request(self, request: Request, response: Response) -> AccessTokenOnlyResponseSchema:
        """새 access 토큰만 발급."""
        client_type = (request.headers.get(settings.CLIENT_TYPE_HEADER) or "").lower()

        if client_type == "web":
            rt = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
            if not rt:
                raise UnauthorizedException("refresh 쿠키가 없습니다.")
            new_access, _ = await self.rotate_token(rt, is_refresh=False)
            return AccessTokenOnlyResponseSchema(access_token=new_access)  #  snake_case

        authz = request.headers.get("Authorization") or ""
        if not authz.startswith("Bearer "):
            raise UnauthorizedException("Bearer refresh 토큰이 없습니다.")
        rt = authz.split(" ", 1)[1]
        new_access, _ = await self.rotate_token(rt, is_refresh=False)
        return AccessTokenOnlyResponseSchema(access_token=new_access)  #  snake_case

    async def rotate_refresh_from_request(self, request: Request, response: Response) -> RefreshTokenOnlyResponseSchema:
        """refresh 토큰 회전."""
        client_type = (request.headers.get(settings.CLIENT_TYPE_HEADER) or "").lower()

        if client_type == "web":
            rt = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
            if not rt:
                raise UnauthorizedException("refresh 쿠키가 없습니다.")
            _, new_refresh = await self.rotate_token(rt, is_refresh=True)
            set_refresh_token_cookie(response, new_refresh)
            return RefreshTokenOnlyResponseSchema(refresh_token=None)  #  snake_case

        authz = request.headers.get("Authorization") or ""
        if not authz.startswith("Bearer "):
            raise UnauthorizedException("Bearer refresh 토큰이 없습니다.")
        rt = authz.split(" ", 1)[1]
        _, new_refresh = await self.rotate_token(rt, is_refresh=True)
        return RefreshTokenOnlyResponseSchema(refresh_token=new_refresh)  #  snake_case

    # ══════════════════════════════════════════════════════════════════════════
    # Driver Mobile — 폰번호 OTP 로그인
    # ══════════════════════════════════════════════════════════════════════════
    # Redis 키:
    #   drvotp:{phone}        = "code|request_id|exp_epoch"  TTL OTP_TTL+grace
    #   drvotp_try:{phone}    = 시도 횟수 카운터
    #   drvotp_send:{phone}   = 발송 횟수 (rate limit)
    #   drvotp_ok:{phone}     = request_id (verify 통과 후 login 단계 token)

    def _drvotp_key(self, phone: str) -> str:    return f"drvotp:{phone}"
    def _drvotp_try(self, phone: str) -> str:    return f"drvotp_try:{phone}"
    def _drvotp_send(self, phone: str) -> str:   return f"drvotp_send:{phone}"
    def _drvotp_ok(self, phone: str) -> str:     return f"drvotp_ok:{phone}"

    async def request_driver_otp(self, *, phone: str):
        """기사 모바일 OTP 발송 (Mock SMS — 콘솔 출력).

        반환: DriverOtpSendResponseSchema(request_id, expires_in_sec)
        ⚠️ 사용자 enumeration 방지 — phone 이 DB 에 없어도 성공 응답.
           실제 user 검증은 driver_login 단계에서.
        """
        from auth.utils.sms import send_otp_sms, normalize_phone
        from auth.schemas.response import DriverOtpSendResponseSchema

        phone_n = normalize_phone(phone)
        if len(phone_n) < 8:
            raise AppException(code="INVALID_PHONE", message="유효하지 않은 폰번호.", status_code=400)

        # rate limit (발송 횟수)
        send_key = self._drvotp_send(phone_n)
        n = await self.redis.incr(send_key)
        if n == 1:
            await self.redis.expire(send_key, int(settings.OTP_BLOCK_SEC))
        if n > settings.OTP_SEND_LIMIT:
            ttl = await self.redis.ttl(send_key)
            ttl = int(settings.OTP_BLOCK_SEC) if (ttl is None or ttl < 0) else int(ttl)
            raise AppException(
                code="TOO_MANY_REQUESTS",
                message="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                status_code=429,
                detail={"send_limit": settings.OTP_SEND_LIMIT, "seconds_left": max(0, ttl)},
            )

        now = int(time.time())
        code = f"{secrets.randbelow(10**6):06d}"
        request_id = uuid.uuid4().hex
        expire_epoch = now + settings.OTP_TTL
        value = f"{code}|{request_id}|{expire_epoch}"

        pipe = self.redis.pipeline(transaction=True)
        pipe.set(self._drvotp_key(phone_n), value, ex=settings.OTP_TTL + settings.OTP_GRACE_SEC)
        pipe.delete(self._drvotp_try(phone_n))
        await pipe.execute()

        # SMS 발송 (mock — 콘솔 출력)
        send_otp_sms(phone=phone_n, code=code, app_name=settings.APP_NAME)

        return DriverOtpSendResponseSchema(
            request_id=request_id, expires_in_sec=settings.OTP_TTL,
        )

    async def verify_driver_otp(self, *, phone: str, request_id: str, code: str):
        """기사 모바일 OTP 검증.

        반환: DriverOtpVerifyResponseSchema(request_id)
        성공 시 drvotp_ok:{phone} = request_id 가 OTP_OK_TTL 동안 보관.
        다음 단계 driver_login 에서 이 ok 키를 검증.
        """
        from auth.utils.sms import normalize_phone
        from auth.schemas.response import DriverOtpVerifyResponseSchema

        phone_n = normalize_phone(phone)

        # 기존 _verify_otp_common 은 email 인자라 — 여기 별도로 구현 (phone 키 prefix 사용)
        otp_key = self._drvotp_key(phone_n)
        try_key = self._drvotp_try(phone_n)

        raw = await self.redis.get(otp_key)
        if not raw:
            raise AppException(
                code="OTP_NOT_FOUND",
                message="요청 내역이 없습니다. 다시 시도해 주세요.",
                status_code=404,
                detail={"attempts_left": settings.OTP_MAX_TRIES, "seconds_left": 0},
            )
        raw = raw.decode() if isinstance(raw, (bytes, bytearray)) else raw

        try:
            saved_code, saved_req, exp = raw.split("|")
            exp = int(exp)
        except Exception:
            raise AppException(code="OTP_CORRUPTED", message="잘못된 상태입니다.", status_code=400)

        now = int(time.time())
        if request_id != saved_req:
            raise AppException(code="OTP_REQUEST_MISMATCH", message="이전 코드이거나 잘못된 요청입니다.", status_code=400)
        if now > (exp + settings.OTP_GRACE_SEC):
            raise AppException(code="OTP_EXPIRED", message="코드가 만료되었습니다.", status_code=400)

        if code != saved_code:
            n = await self.redis.incr(try_key)
            await self.redis.expire(try_key, max(1, (exp + settings.OTP_GRACE_SEC) - now))
            attempts_left = max(0, settings.OTP_MAX_TRIES - int(n))
            if int(n) >= settings.OTP_MAX_TRIES:
                pipe = self.redis.pipeline(transaction=True)
                pipe.delete(otp_key)
                pipe.delete(try_key)
                await pipe.execute()
                raise AppException(
                    code="OTP_TOO_MANY_TRIES",
                    message="시도 횟수가 초과되었습니다. 인증 코드를 재발송해 주세요.",
                    status_code=429,
                    detail={"attempts_left": 0},
                )
            raise AppException(
                code="OTP_NOT_MATCH",
                message="코드가 일치하지 않습니다.",
                status_code=400,
                detail={"attempts_left": attempts_left},
            )

        # OK 키 발급 (login 단계에서 검증)
        ok_ttl = int(getattr(settings, "OTP_OK_TTL", 900))
        await self.redis.set(self._drvotp_ok(phone_n), request_id, ex=ok_ttl)

        return DriverOtpVerifyResponseSchema(request_id=request_id)

    async def driver_login(
        self,
        request: Request,
        response: Response,
        *,
        phone: str,
        request_id: str,
    ) -> TokenResponseSchema:
        """기사 모바일 최종 로그인. ok 키 검증 + user.phone 으로 user 찾기 + tokens 발급.

        에러:
          - DRIVER_OTP_NOT_VERIFIED: verify 단계 미완 (또는 만료)
          - DRIVER_NOT_REGISTERED: 폰번호로 등록된 driver 없음 (관리자가 미리 driver 추가 필요)
          - DRIVER_INACTIVE: user.is_active=False
        """
        from auth.utils.sms import normalize_phone

        phone_n = normalize_phone(phone)

        # 1) ok 키 검증
        ok_raw = await self.redis.get(self._drvotp_ok(phone_n))
        if not ok_raw:
            raise AppException(
                code="DRIVER_OTP_NOT_VERIFIED",
                message="OTP 인증이 만료되었거나 완료되지 않았습니다. 다시 시도해 주세요.",
                status_code=400,
            )
        ok_req = ok_raw.decode() if isinstance(ok_raw, (bytes, bytearray)) else ok_raw
        if ok_req != request_id:
            raise AppException(
                code="DRIVER_OTP_REQUEST_MISMATCH",
                message="요청 정보가 일치하지 않습니다. 처음부터 다시 시도해 주세요.",
                status_code=400,
            )

        # 2) user 찾기 (phone 으로)
        user = await self.user_repository.get_user_by_phone(phone_n)
        if not user:
            raise AppException(
                code="DRIVER_NOT_REGISTERED",
                message="등록되지 않은 폰번호입니다. 관리자에게 문의해주세요.",
                status_code=404,
            )
        if not user.is_active:
            raise AppException(
                code="DRIVER_INACTIVE",
                message="비활성 계정입니다. 관리자에게 문의해주세요.",
                status_code=403,
            )

        # 3) ok 키 즉시 삭제 (단회용)
        await self.redis.delete(self._drvotp_ok(phone_n))

        # 4) UserResponseSchema 변환 후 기존 login_user 위임 (세션/토큰 발급)
        user_schema = UserResponseSchema.model_validate(user)
        return await self.login_user(request, response, user_schema)