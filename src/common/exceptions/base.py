from __future__ import annotations
from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, status

JsonObj = Dict[str, Any]
MsgType = Union[str, JsonObj]


class AppException(HTTPException):
    def __init__(
        self,
        *,
        code: str,
        message: MsgType,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: Optional[JsonObj] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail_obj = detail
        super().__init__(status_code=status_code, detail=self._http_detail())

    def _http_detail(self) -> Any:
        base = {"code": self.code, "message": self.message, "status_code": self.status_code}
        if self.detail_obj is not None:
            base["detail"] = self.detail_obj
        return base

    def to_dict(self) -> JsonObj:
        payload: JsonObj = {
            "error": {
                "code": self.code,
                "message": self.message,
                "status_code": self.status_code,
            }
        }
        if self.detail_obj is not None:
            payload["error"]["detail"] = self.detail_obj
        return payload


class NotFoundException(AppException):
    def __init__(self, target: str = "리소스", *, message: Optional[str] = None, detail: Optional[JsonObj] = None):
        super().__init__(
            code="NOT_FOUND",
            message=message or f"{target}을(를) 찾을 수 없습니다.",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized", *, detail: Optional[JsonObj] = None):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden", *, detail: Optional[JsonObj] = None):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ConflictException(AppException):
    def __init__(self, message: str = "Conflict occurred", *, detail: Optional[JsonObj] = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class BadRequestException(AppException):
    def __init__(self, message: MsgType = "Bad request", *, detail: Optional[JsonObj] = None, code: str = "BAD_REQUEST"):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
