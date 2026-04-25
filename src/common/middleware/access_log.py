"""
요청/응답 Access 로그를 구조적으로 기록
- method/path/status/duration(ms) 등을 한 줄로
"""

from __future__ import annotations
import time
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger("access")

NOISE_PATHS = {"/health", "/metrics"}
STATIC_PREFIXES = ("/public/", "/static/")

# 운영 환경에서도 무조건 해당 로그는 찍히고
# 나머지는 서비스로직에서의 로그는 waring이상만 찍힌다.
# 서비스 로직까지 다 찍히게 할 경우, 로그 데이터가 너무 많이 쌓인다.
class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 소음 경로는 로깅을 생략하고 통과
        if path in NOISE_PATHS or path.startswith(STATIC_PREFIXES):
            return await call_next(request)

        start = time.perf_counter()
        method = request.method

        response = await call_next(request)

        duration_ms = int((time.perf_counter() - start) * 1000)

        # 필요하면 여기서 user_id를 다시 바인딩해도 됨
        # from common.utils.contextvars import user_id_ctx_var
        # uid = user_id_ctx_var.get(None)
        # structlog.contextvars.bind_contextvars(user_id=uid)

        logger.info(
            "http_access",
            method=method,
            path=path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
