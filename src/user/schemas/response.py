# src/user/schemas/response.py
from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import EmailStr
from common.schemas.base import ResponseSchema
from common.schemas.nested import FileNestedSchema
from user.const.roles import RolesEnum


# ─────────────────────────────────────────────
# 서브 응답 스키마들(관계용)
# ─────────────────────────────────────────────
class UserTenantRowResponseSchema(ResponseSchema):
    id: int
    tenant_id: int
    tenant_name: Optional[str] = None
    permission_group_id: Optional[int] = None


# ─────────────────────────────────────────────
# 목록용: 모든 관계 포함(초기에는 상세와 동일하게 둠)
# ─────────────────────────────────────────────
class UserListItemResponseSchema(ResponseSchema):
    id: int
    email: Optional[EmailStr] = None
    role: RolesEnum
    name: Optional[str] = None
    phone: Optional[str] = None

    #  OAuth 관련
    auth_provider: str = "email"  # email, google, kakao, apple
    
    #  알림 설정
    notification_email: Optional[str] = None
    event_notification_enabled: bool = False

    #  언어 설정
    language: Optional[str] = "auto"

    tenants: List[UserTenantRowResponseSchema] = []
    files: List[FileNestedSchema] = []


# ─────────────────────────────────────────────
# 상세용: 현재는 목록과 필드 동일(추후 상세만 확장 가능)
# ─────────────────────────────────────────────
class UserDetailResponseSchema(UserListItemResponseSchema):
    pass


# ─────────────────────────────────────────────
# (User Depends 용도) - 인증 토큰 검증 후 최소 정보
# ─────────────────────────────────────────────
class UserResponseSchema(ResponseSchema):
    id: int
    email: Optional[EmailStr] = None
    role: RolesEnum
    auth_provider: str = "email"  #  OAuth 관련


class TokenPayloadResponseSchema(ResponseSchema):
    id: int
    sid: Optional[str] = None
    did: Optional[str] = None
    jti: Optional[str] = None
    type: str
    iat: Optional[int] = None
    exp: int


# ─────────────────────────────────────────────
# 삭제 응답 (Stripe 스타일)
# ─────────────────────────────────────────────
class UserDeleteResponseSchema(ResponseSchema):
    """
    사용자 삭제 응답 (Stripe 스타일)
    
    - id: 삭제된 사용자 ID
    - object: 리소스 타입 (항상 "user")
    - deleted: 삭제 여부
    - soft_deleted: 소프트 삭제 여부 (FK 참조로 하드 삭제 실패 시 True)
    - teams_cleaned: 멤버 0명이 되어 정리된 팀 수
    """
    id: int
    object: Literal["user"] = "user"
    deleted: bool = True
    soft_deleted: bool = False
    teams_cleaned: int = 0