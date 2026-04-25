# common/middleware/auth.py
import logging
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from auth.utils.tokens import decode_jwt_token
from common.utils.contextvars import user_id_ctx_var

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """
        - OPTIONS(프리플라이트)는 무조건 패스 (CORS용)
        - Basic 은 패스 (로그인 엔드포인트용)
        - Bearer 가 있어도: 검증 실패/만료여도 예외를 던지지 않고 그냥 통과
          (실제 권한 체크는 각 라우터/디펜던시에서 401 처리)
        - 여기서 예외를 던지면 CORS 헤더가 빠진 응답이 될 수 있어
          브라우저가 XHR 에러로 막아버리므로, 절대 raise 하지 않음.
        """
        try:
            if request.scope.get("type") != "http":
                return await call_next(request)
            if request.method == "OPTIONS":
                return await call_next(request)

            auth_header = request.headers.get("Authorization", "")

            if auth_header.startswith("Basic "):
                user_id_ctx_var.set(None)
                structlog.contextvars.bind_contextvars(user_id=None)
                return await call_next(request)

            if not auth_header.startswith("Bearer "):
                user_id_ctx_var.set(None)
                structlog.contextvars.bind_contextvars(user_id=None)
                return await call_next(request)

            token = auth_header[7:].strip()
            if not token:
                user_id_ctx_var.set(None)
                structlog.contextvars.bind_contextvars(user_id=None)
                return await call_next(request)

            try:
                user = decode_jwt_token(token)
                uid = getattr(user, "id", None)
                user_id_ctx_var.set(uid)
                # structlog 컨텍스트에도 바인딩 → 이후 모든 로그에서 자동 병합
                structlog.contextvars.bind_contextvars(user_id=uid)
                request.state.user = user  # 선택: 라우터에서 접근 용이
            except Exception as e:
                logger.debug(f"[AUTH-MW] Bearer decode failed: {e}")
                user_id_ctx_var.set(None)
                structlog.contextvars.bind_contextvars(user_id=None)

            return await call_next(request)

        except Exception as e:
            logger.warning(f"[AUTH-MW] unexpected error: {e}")
            return await call_next(request)
