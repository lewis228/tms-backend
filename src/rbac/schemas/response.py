# rbac/schemas/response.py
from __future__ import annotations
from typing import Dict, List, Optional, Literal
from pydantic import Field
from common.schemas.base import ResponseSchema

# ──────────────── 모델 직변환용(옵션) ────────────────
class PermissionResponseSchema(ResponseSchema):
    id: int
    code: str
    label: str
    category: Optional[str] = None


class PermissionGroupResponseSchema(ResponseSchema):
    id: int
    name: str
    is_admin: bool
    # 필요시 주석 해제
    # permissions: List[PermissionResponseSchema] = []


# ──────────────── RBAC 공통 메타 ────────────────
class RbacMetaResponseSchema(ResponseSchema):
    """
    RBAC 응답 내부 메타데이터
    - 실제 모델 컬럼명과 일치:
      * permission_group_id  ↔ UserTenantModel.permission_group_id
      * is_admin             ↔ PermissionGroupModel.is_admin
      * version              ↔ PermissionGroupModel.version (그룹 권한 코드셋 버전)  # NEW
    """
    permission_group_id: Optional[int] = None
    is_admin: bool = False
    version: Optional[int] = None  # NEW: 캐시/동기화 확인용 그룹 버전


# ──────────────── 단일 엔드포인트 응답 (/rbac/me) ────────────────
class RbacMeResponseSchema(ResponseSchema):
    """
    /rbac/me
    - codes: 사용자가 '실제로 가진' 권한 코드 리스트
    - abilities: 시스템의 모든 권한 코드에 대해 True/False 판정 결과
    - rbac: 그룹/어드민 메타(+ version)
    """
    codes: List[str] = Field(default_factory=list)
    abilities: Dict[str, bool] = Field(default_factory=dict)
    rbac: RbacMetaResponseSchema
    excluded_attribute_ids: List[int] = Field(default_factory=list)


# ──────────────── API 응답 (그룹 관리) ────────────────
class PermissionGroupListItemResponseSchema(ResponseSchema):
    """그룹 목록 아이템"""
    id: int
    name: str
    is_admin: bool
    is_system: bool
    system_key: Optional[str] = None  # 'ADMIN'|'MEMBER'|'VIEWER'|None
    members: int = 0                  # 멤버 수
    code_count: int = 0               # 매핑된 코드 수
    version: Optional[int] = None     # NEW: 그룹 권한 버전(코드 변경 시 증가)


class PermissionGroupDetailResponseSchema(PermissionGroupListItemResponseSchema):
    """단일 그룹 상세(코드 목록 포함)"""
    codes: List[str] = Field(default_factory=list)
    excluded_attribute_ids: List[int] = Field(default_factory=list)
    # (상위 클래스의 version 필드가 그대로 포함됩니다)


# ──────────────── 그룹 작업 응답 (Stripe 스타일) ────────────────
class PermissionGroupRenameResponseSchema(ResponseSchema):
    """권한 그룹 이름 변경 응답"""
    id: int
    object: Literal["permission_group"] = "permission_group"
    renamed: bool = True
    name: str  # 변경된 이름


class PermissionGroupDeleteResponseSchema(ResponseSchema):
    """권한 그룹 삭제 응답"""
    id: int
    object: Literal["permission_group"] = "permission_group"
    deleted: bool = True