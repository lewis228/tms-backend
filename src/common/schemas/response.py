# src/common/schemas/response.py
from __future__ import annotations

from typing import Optional
from pydantic import Field
from common.schemas.base import ResponseSchema  # ← 우리가 만든 공통 베이스

class SuccessResponseSchema(ResponseSchema):
    """
    표준 성공 응답 스키마.

    - success: 항상 True (성공 응답 식별자)
    - message: 선택적 성공 메시지
    - status_code: HTTP 상태 코드(기본 200). FastAPI가 실제 HTTP 코드를 따로 설정하더라도
      응답 바디에도 담아두면 클라이언트에서 로깅/분기 일관성 유지에 유리.
    """
    success: bool = Field(default=True, description="성공 여부(항상 True)")
    message: Optional[str] = Field(default=None, description="성공 메시지(선택)")
    status_code: int = Field(default=200, ge=200, lt=600, description="HTTP 상태 코드")

    # ResponseSchema 에서 이미 다음을 공통 적용:
    # - from_attributes=True (ORM → Pydantic 변환)
    # - extra="ignore"       (여분 필드 무시)
    # - validate_assignment=False

    # --- 편의 헬퍼 ---
    @classmethod
    def ok(cls, message: Optional[str] = None) -> "SuccessResponseSchema":
        """200 OK 성공 응답을 빠르게 생성."""
        return cls(success=True, message=message, status_code=200)

    @classmethod
    def created(cls, message: Optional[str] = None) -> "SuccessResponseSchema":
        """201 Created 성공 응답을 빠르게 생성."""
        return cls(success=True, message=message, status_code=201)

    @classmethod
    def accepted(cls, message: Optional[str] = None) -> "SuccessResponseSchema":
        """202 Accepted 성공 응답을 빠르게 생성."""
        return cls(success=True, message=message, status_code=202)
