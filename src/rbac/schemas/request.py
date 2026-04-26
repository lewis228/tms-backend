# rbac/schemas/request.py
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import Field
from common.pagination.schemas.pagination_request import BasePaginationSchema
from common.schemas.base import RequestSchema

# ─────────────────────────────────────────────────────────
# 그룹 생성/수정/코드 패치 요청 스키마
# ─────────────────────────────────────────────────────────

class PermissionGroupCreateRequestSchema(RequestSchema):
    """커스텀 권한 그룹 생성"""
    name: str = Field(min_length=1, max_length=255, description="그룹명(중복 허용)")
    codes: Optional[List[str]] = Field(default=None, description="초기 권한 코드 목록(옵션)")
    excluded_attribute_ids: Optional[List[int]] = Field(default=None, description="접근 제외 속성 ID 목록")


class PermissionGroupRenameRequestSchema(RequestSchema):
    """권한 그룹 이름 변경"""
    name: str = Field(min_length=1, max_length=255, description="새 그룹명")


class PermissionGroupSetCodesRequestSchema(RequestSchema):
    """그룹 권한 코드 '완전 교체'"""
    codes: List[str] = Field(default_factory=list, description="대체할 전체 권한 코드 목록")
    excluded_attribute_ids: Optional[List[int]] = Field(default=None, description="접근 제외 속성 ID 목록(None=변경 없음)")


class PermissionGroupPatchCodesRequestSchema(RequestSchema):
    """그룹 권한 코드 '증감 패치'"""
    op: Literal["add", "remove"] = Field(description="작업 종류: add/remove")
    codes: List[str] = Field(default_factory=list, description="추가/제거할 권한 코드 목록")

# ─────────────────────────────────────────────────────────
# ▼ 신규: 커서 페이지네이션 요청
# ─────────────────────────────────────────────────────────
class PaginatePermissionGroupRequest(BasePaginationSchema):
    """
    권한 그룹 목록 커서 페이지네이션 요청
    - BasePaginationSchema 상속(page/take, where__id__*, order__id)
    """
    # 정렬 옵션
    order__name: Optional[Literal["ASC", "DESC"]] = None
    # 필터 옵션
    where__name__i_like: Optional[str] = Field(default=None, description="그룹명 부분검색(대소문자 무시)")
    where__is_system__equal: Optional[bool] = Field(default=None, description="시스템 그룹 여부 필터")
    where__system_key__equal: Optional[str] = Field(default=None, description="ADMIN|MEMBER|VIEWER|NULL")

