"""미들웨어.

등록 순서 (main.py 에서 add_middleware 역순):
1. CORS
2. RequestLoggingMiddleware
3. TenantContextMiddleware

TenantContextMiddleware: JWT/X-Tenant-ID 를 보고 ContextVar `tenant_id_ctx` 설정.
실제 인증/권한 체크는 Depends(CurrentUser) 에서 하고 여기서는 컨텍스트 주입만.
"""
from __future__ import annotations

import time
import uuid
from contextvars import ContextVar

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings
from app.core.logging import get_logger

tenant_id_ctx: ContextVar[str | None] = ContextVar("tenant_id_ctx", default=None)
request_id_ctx: ContextVar[str | None] = ContextVar("request_id_ctx", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id_ctx", default=None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.log = get_logger("http")

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            self.log.exception(
                "request.failed",
                method=request.method,
                path=request.url.path,
                request_id=rid,
                elapsed_ms=round(elapsed, 2),
            )
            raise
        else:
            elapsed = (time.perf_counter() - start) * 1000
            self.log.info(
                "request.completed",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                request_id=rid,
                elapsed_ms=round(elapsed, 2),
            )
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_ctx.reset(token)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """JWT/X-Tenant-ID 디코드 → ContextVar 주입.

    JWT 검증 자체는 Depends(CurrentUser) 가 다시 한다 — 여기서는 best-effort.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant_token = None
        user_token = None
        try:
            tenant_id, user_id = self._extract(request)
            if tenant_id:
                tenant_token = tenant_id_ctx.set(tenant_id)
            if user_id:
                user_token = user_id_ctx.set(user_id)
            return await call_next(request)
        finally:
            if tenant_token is not None:
                tenant_id_ctx.reset(tenant_token)
            if user_token is not None:
                user_id_ctx.reset(user_token)

    @staticmethod
    def _extract(request: Request) -> tuple[str | None, str | None]:
        auth = request.headers.get("Authorization", "")
        jwt_tenant: str | None = None
        jwt_user: str | None = None
        if auth.startswith("Bearer "):
            try:
                payload = jwt.decode(
                    auth[7:], settings.jwt_secret, algorithms=["HS256"]
                )
                jwt_tenant = payload.get("tenant_id")
                jwt_user = payload.get("sub")
            except jwt.PyJWTError:
                pass
        header_tenant = request.headers.get("X-Tenant-ID")
        # JWT 우선, header 는 SUPER_ADMIN 일 때 의미 — 실제 권한 체크는 Depends 단계
        return (jwt_tenant or header_tenant, jwt_user)
