"""
base.py
──────────────────────────────────────────────
애플리케이션 전역에서 사용하는 "비즈니스 예외" 정의 파일.

핵심 목적:
  - 일관된 예외 응답 형식(JSON)을 보장한다.
  - 모든 도메인에서 raise 시 동일한 구조를 유지한다.
  - HTTP 상태코드, 코드명(code), 사용자 메시지(message), 상세(detail)를 포함한다.

사용 예시:
    raise NotFoundException("Product")
    raise UnauthorizedException("Access token expired")
    raise AppException(code="INVALID_STATUS", message="상태값이 유효하지 않습니다.")
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, status


# 타입 별칭
JsonObj = Dict[str, Any]
MsgType = Union[str, JsonObj]


class AppException(HTTPException):
    """
    공통 비즈니스 예외 클래스 (모든 도메인에서 공통 사용)

    특징:
      • FastAPI의 HTTPException을 상속받아 status_code 사용 가능.
      • JSON 응답은 항상 아래 형식으로 변환된다:
          {
            "error": {
              "code": "ERROR_CODE",
              "message": "사람이 읽을 수 있는 메시지",
              "status_code": 400,
              "detail": {...}   # 선택적 부가정보
            }
          }
      • message는 str 또는 dict 모두 허용 (i18n 적용 등 확장성 고려)
    """

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

        # FastAPI 기본 HTTPException.detail 필드는 최소 정보만 전달
        super().__init__(status_code=status_code, detail=self._http_detail())

    def _http_detail(self) -> Any:
        """FastAPI 기본 에러핸들러가 참조할 최소 정보"""
        base = {"code": self.code, "message": self.message, "status_code": self.status_code}
        if self.detail_obj is not None:
            base["detail"] = self.detail_obj
        return base

    def to_dict(self) -> JsonObj:
        """커스텀 핸들러에서 JSON 응답으로 직렬화할 때 사용"""
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


# ──────────────────────────────────────────────────────────────
# 파생 예외 클래스들
# ──────────────────────────────────────────────────────────────

class NotFoundException(AppException):
    """404: 요청한 리소스가 존재하지 않을 때"""
    def __init__(self, target: str = "리소스", *, message: Optional[str] = None, detail: Optional[JsonObj] = None):
        super().__init__(
            code="NOT_FOUND",
            message=message or f"{target}을(를) 찾을 수 없습니다.",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class UnauthorizedException(AppException):
    """401: 인증 실패 (로그인 필요, 토큰 만료 등)"""
    def __init__(self, message: str = "Unauthorized", *, detail: Optional[JsonObj] = None):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class ForbiddenException(AppException):
    """403: 권한 부족 (인가 실패, 접근 불가)"""
    def __init__(self, message: str = "Forbidden", *, detail: Optional[JsonObj] = None):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ConflictException(AppException):
    """409: 중복 또는 충돌 상황"""
    def __init__(self, message: str = "Conflict occurred", *, detail: Optional[JsonObj] = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

class BadRequestException(AppException):
    """400: 잘못된 요청(비즈니스 규칙 위반/사전조건 불충족 등)"""
    def __init__(self, message: MsgType = "Bad request", *, detail: Optional[JsonObj] = None, code: str = "BAD_REQUEST"):
        super().__init__(
            code=code,  # 필요하면 세부 코드로 오버라이드 가능: e.g., "INVALID_STATE", "PRECONDITION_FAILED"
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
