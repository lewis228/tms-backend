# src/customer/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field, EmailStr, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class CustomerCreateRequest(RequestSchema):
    """고객사 생성 DTO."""
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    billing_address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: EmailStr | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=3000)


class CustomerUpdateRequest(RequestSchema):
    """고객사 수정 DTO (부분 수정 허용)."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    billing_address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: EmailStr | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=3000)


class PaginateCustomerRequest(BasePaginationSchema):
    """
    고객사 목록 커서 페이지네이션 DTO
    - 기본 정렬: id ASC (커서 페이징 안정성)
    - include_inactive=True 이면 비활성까지 포함
    - where__* 필터들은 값이 있을 때만 자동 적용
    """
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'

    include_inactive: bool = False

    # 선택 필터
    where__name__i_like: Optional[str] = None
    where__code__i_like: Optional[str] = None
    where__contact_email__i_like: Optional[str] = None
    where__contact_phone__i_like: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Bulk Request DTOs
# ═══════════════════════════════════════════════════════════════

class CustomerBulkCreateRequest(RequestSchema):
    """고객사 벌크 생성 (최대 100개)."""
    items: List[CustomerCreateRequest] = Field(..., min_length=1, max_length=100)


class CustomerBulkUpdateItem(RequestSchema):
    """벌크 수정 개별 항목 — id 필수."""
    id: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=64)
    billing_address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=100)
    contact_email: EmailStr | None = Field(default=None, max_length=128)
    contact_phone: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=3000)


class CustomerBulkUpdateRequest(RequestSchema):
    """고객사 벌크 수정 DTO."""
    items: List[CustomerBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class CustomerBulkDeleteRequest(RequestSchema):
    """고객사 벌크 삭제 (최대 100개, ID 중복 제거)."""
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
