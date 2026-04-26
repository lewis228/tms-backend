"""
handlers.py
──────────────────────────────────────────────
FastAPI 전역 예외 핸들러 모음.

핵심 역할:
  • 모든 예외를 구조화된 JSON으로 응답한다.
  • 로그는 structlog로 기록하여 관측/집계가 용이하도록 한다.
  • Request, Validation, HTTPException, 비즈니스(AppException) 등을 일관 처리.

적용 위치:
  main.py 에서 다음과 같이 등록:
      app.add_exception_handler(AppException, app_exception_handler)
      app.add_exception_handler(StarletteHTTPException, http_exception_handler)
      app.add_exception_handler(RequestValidationError, validation_exception_handler)
      app.add_exception_handler(Exception, global_exception_handler)
"""

from __future__ import annotations
import json
from decimal import Decimal
import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import asyncio
from sqlalchemy.exc import SQLAlchemyError, DBAPIError
from .base import AppException

logger = structlog.get_logger()


# ──────────────────────────────────────────────────────────────
# 내부 유틸: 클라이언트 IP 추출
# ──────────────────────────────────────────────────────────────
def _client_ip(request: Request) -> str | None:
    """요청 객체에서 클라이언트 IP 주소 추출 (없으면 None)"""
    return request.client.host if request.client else None


# ──────────────────────────────────────────────────────────────
# 내부 유틸: Decimal 등 직렬화 불가 타입 처리
# ──────────────────────────────────────────────────────────────
class CustomJSONEncoder(json.JSONEncoder):
    """Decimal, tuple 등 JSON 직렬화 불가 타입 처리"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, tuple):
            return list(obj)
        return super().default(obj)


def _serialize_for_json(obj):
    """
    재귀적으로 dict/list 내부의 Decimal, tuple 등을 변환
    - JSONResponse가 직렬화할 수 있도록 사전 처리
    """
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, tuple):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, Decimal):
        return str(obj)
    else:
        return obj


# ──────────────────────────────────────────────────────────────
# 1. AppException (비즈니스 예외)
# ──────────────────────────────────────────────────────────────
async def app_exception_handler(request: Request, exc: AppException):
    """
    AppException 발생 시 처리 핸들러
    - 모든 커스텀 예외(AppException 기반)는 이 경로로 들어온다.
    - 구조적 로그(경로, 메서드, 코드, 상태, 사용자ID 등)를 남긴다.
    """
    logger.warning(
        "app_exception",
        code=exc.code,
        status=exc.status_code,
        path=request.url.path,
        method=request.method,
        client_ip=_client_ip(request),
        detail=getattr(exc, "detail_obj", None),
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


# ──────────────────────────────────────────────────────────────
# 2. Validation Error (입력 검증 실패)
# ──────────────────────────────────────────────────────────────
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Pydantic 기반 입력 검증 실패 처리
    - FastAPI 기본 메시지를 통일된 JSON 스키마로 가공.
    - 구조적 로그에 오류 목록(errors)을 남긴다.
    """
    def sanitize_errors(errors):
        """ctx 내부의 불필요한 정보 제거 및 문자열 변환"""
        cleaned = []
        for e in errors:
            e = e.copy()
            ctx = e.get("ctx")
            if ctx and "error" in ctx:
                e["msg"] = str(ctx["error"])
                e.pop("ctx", None)
            cleaned.append(e)
        return cleaned

    details = {"errors": sanitize_errors(exc.errors())}
    
    # Decimal, tuple 등 직렬화 불가 타입 처리
    details = _serialize_for_json(details)
    
    logger.info(
        "validation_error",
        status=422,
        path=request.url.path,
        method=request.method,
        client_ip=_client_ip(request),
        details=details,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "status_code": 422,
                "detail": details,
            }
        },
    )


# ──────────────────────────────────────────────────────────────
# 3. Starlette 기본 HTTPException (ex. raise HTTPException)
# ──────────────────────────────────────────────────────────────
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    FastAPI/Starlette 기본 HTTPException 처리
    - 예: raise HTTPException(status_code=404, detail="Not found")
    """
    logger.warning(
        "http_exception",
        status=exc.status_code,
        path=request.url.path,
        method=request.method,
        client_ip=_client_ip(request),
        detail=str(exc.detail),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "status_code": exc.status_code,
            }
        },
    )


# ──────────────────────────────────────────────────────────────
# 4. 미처리(Unhandled) 예외 (예상치 못한 런타임 오류)
# ──────────────────────────────────────────────────────────────
async def global_exception_handler(request: Request, exc: Exception):
    """
    예상치 못한 모든 예외 처리 (ZeroDivisionError 등)
    - 스택트레이스와 함께 ERROR 레벨 로그 출력.
    - 사용자에게는 내부 오류 메시지만 노출(보안 고려).
    """
    logger.exception(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        client_ip=_client_ip(request),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "서버 내부 오류가 발생했습니다.",
                "status_code": 500,
            }
        },
    )

# ──────────────────────────────────────────────────────────────
# X. asyncio.TimeoutError (앱 레벨 타임아웃)
# ──────────────────────────────────────────────────────────────
async def timeout_exception_handler(request: Request, exc: asyncio.TimeoutError):
    """
    TimedAsyncSession에서 걸린 앱 레벨 타임아웃.
    보안상 내부 사유는 숨기고, 504로 응답.
    """
    logger.warning(
        "timeout_error",
        status=504,
        path=request.url.path,
        method=request.method,
        client_ip=_client_ip(request),
    )
    return JSONResponse(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        content={
            "error": {
                "code": "TIMEOUT",
                "message": "요청 처리 시간이 초과되었습니다.",
                "status_code": 504,
            }
        },
    )

# ──────────────────────────────────────────────────────────────
# Y. SQLAlchemy / MySQL 예외 매핑
# ──────────────────────────────────────────────────────────────
def _mysql_err_code(exc: BaseException) -> int | None:
    """
    SQLAlchemy 예외에서 MySQL 에러코드(int) 추출 시도.
    - 대부분 DBAPIError.orig.args[0] 형태로 코드가 들어있음.
    """
    try:
        if isinstance(exc, DBAPIError) and exc.orig is not None:
            args = getattr(exc.orig, "args", None)
            if args and isinstance(args, (list, tuple)) and args:
                if isinstance(args[0], int):
                    return args[0]
    except Exception:
        pass
    return None

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """
    주로 DB 레벨 시간제한/락 타임아웃을 사용자 친화적인 상태코드로 변환.
    """
    code = _mysql_err_code(exc)
    # MySQL 주요 코드 매핑
    # 3024: MAX_EXECUTION_TIME 초과 (SELECT 제한) → 504
    # 1205: Lock wait timeout → 409
    # 1213: Deadlock found → 409
    # 1317: Query interrupted → 504 (또는 499로도 운영 가능)
    if code in (3024, 1317):
        http_status = status.HTTP_504_GATEWAY_TIMEOUT
        err_code = "DB_TIMEOUT"
        message = "데이터베이스 처리 시간이 초과되었습니다."
    elif code in (1205, 1213):
        http_status = status.HTTP_409_CONFLICT
        err_code = "DB_LOCK_CONFLICT"
        message = "데이터베이스 잠금 경합이 발생했습니다. 잠시 후 다시 시도해주세요."
    else:
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        err_code = "DB_ERROR"
        message = "데이터베이스 오류가 발생했습니다."

    logger.warning(
        "sqlalchemy_exception",
        status=http_status,
        mysql_code=code,
        path=request.url.path,
        method=request.method,
        client_ip=_client_ip(request),
        detail=str(getattr(exc, "orig", exc)),
    )

    return JSONResponse(
        status_code=http_status,
        content={
            "error": {
                "code": err_code,
                "message": message,
                "status_code": http_status,
            }
        },
    )