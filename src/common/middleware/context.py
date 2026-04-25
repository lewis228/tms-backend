"""
요청별 request_id를 컨텍스트에 주입하고, 응답 헤더에 X-Request-ID를 추가
- AuthMiddleware가 user_id를 바인딩하면 processors가 자동 병합
"""

from __future__ import annotations
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from common.utils.contextvars import request_id_ctx_var


class LogContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1) X-Request-ID 헤더 우선, 없으면 uuid 생성
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_ctx_var.set(request_id)

        # 2) 다음으로 진행
        response = await call_next(request)

        # 3) 응답 헤더에 반영 (클라이언트-서버 추적 접점)
        response.headers["X-Request-ID"] = request_id
        return response
