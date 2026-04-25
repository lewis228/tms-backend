"""TMS 예외 계층 + FastAPI 핸들러.

응답 표준: {"error": {"code": "ERR_*", "message": "...", "details": {...}}}
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


class TMSException(Exception):
    code: str = "ERR_INTERNAL"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class NotFoundError(TMSException):
    code = "ERR_NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND
    message = "Resource not found"


class ConflictError(TMSException):
    code = "ERR_CONFLICT"
    status_code = status.HTTP_409_CONFLICT
    message = "Resource conflict"


class ValidationError(TMSException):
    code = "ERR_VALIDATION"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "Validation failed"


class InvalidStateTransitionError(TMSException):
    code = "ERR_INVALID_STATE_TRANSITION"
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "Invalid state transition"


class UnauthorizedError(TMSException):
    code = "ERR_UNAUTHORIZED"
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Unauthorized"


class ForbiddenError(TMSException):
    code = "ERR_FORBIDDEN"
    status_code = status.HTTP_403_FORBIDDEN
    message = "Forbidden"


class TenantMismatchError(ForbiddenError):
    code = "ERR_TENANT_MISMATCH"
    message = "Tenant context mismatch"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TMSException)
    async def _tms_handler(_req: Request, exc: TMSException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"ERR_HTTP_{exc.status_code}",
                    "message": exc.detail if isinstance(exc.detail, str) else "HTTP error",
                    "details": exc.detail if isinstance(exc.detail, dict) else {},
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_req: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "ERR_VALIDATION",
                    "message": "Request validation failed",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_handler(_req: Request, _exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "ERR_INTEGRITY",
                    "message": "Database integrity violation",
                    "details": {},
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def _db_handler(_req: Request, _exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {"code": "ERR_DATABASE", "message": "Database error", "details": {}}
            },
        )
