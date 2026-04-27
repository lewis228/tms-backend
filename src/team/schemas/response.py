# src/team/schemas/response.py
from __future__ import annotations
from typing import Optional, Literal, List
from datetime import datetime

from common.schemas.base import ResponseSchema
from common.schemas.nested import (
    UserNestedWithFilesSchema,
    PermissionGroupNestedSchema,
    FileNestedSchema,
)


class TeamResponseSchema(ResponseSchema):
    """단일 팀 응답(경량) — id, name, 온보딩 상태"""
    id: int
    name: str
    # 온보딩 상태
    onboarding_step1_done: bool = False
    onboarding_step2_done: bool = False
    onboarding_step3_done: bool = False
    onboarding_completed: bool = False


class TeamListItemResponseSchema(TeamResponseSchema):
    """마이 팀 목록의 한 항목(목록 카드용)"""
    files: List[FileNestedSchema] = []


class TeamDetailResponseSchema(TeamResponseSchema):
    """
    상세 응답 — 팀 설정 페이지에서 사용
    """
    # 팀 정보
    memo: Optional[str] = None
    timezone: Optional[str] = None
    image_url: Optional[str] = None

    # 회사 정보
    company_name: Optional[str] = None
    registration_number: Optional[str] = None
    address: Optional[str] = None
    representative_name: Optional[str] = None
    phone_number: Optional[str] = None

    # 표시 설정
    currency: Optional[str] = None
    decimal_places: int = 0
    product_info_display: Optional[str] = None
    product_info_template: Optional[str] = None

    # 엑셀 가져오기
    excel_product_identification: Optional[str] = None

    # 바코드 스캔
    gs1_gtin_enabled: bool = False

    # 파일 (이미지 등)
    files: List[FileNestedSchema] = []


# ─────────────────────────────────────────────────────────
# ▼ 커서 페이지네이션: 멤버 응답 (서비스 변환기 불필요)
# ─────────────────────────────────────────────────────────
class UserTeamResponseSchema(ResponseSchema):
    """
    팀 멤버 한 명의 응답 형태
    - ORM: UserTeamModel 한 줄을 from_attributes=True로 직변환
    - user / permission_group 관계는 중첩 ResponseSchema로 반환
    """
    id: int
    # FK 원본
    user_id: int
    permission_group_id: Optional[int] = None

    # 중첩(평탄화 제거) — 프로필 이미지(files) 포함
    user: Optional[UserNestedWithFilesSchema] = None
    permission_group: Optional[PermissionGroupNestedSchema] = None


# ─────────────────────────────────────────────────────────
# ▼ 팀 작업 응답 스키마 (Stripe 스타일)
# ─────────────────────────────────────────────────────────
class TeamRenameResponseSchema(ResponseSchema):
    """팀 이름 변경 응답"""
    id: int
    object: Literal["team"] = "team"
    renamed: bool = True
    name: str  # 변경된 이름


class TeamDeleteResponseSchema(ResponseSchema):
    """팀 삭제(소프트) 응답"""
    id: int
    object: Literal["team"] = "team"
    deleted: bool = True
    purge_at: Optional[datetime] = None  # 영구 삭제 예정 시각


class TeamReactivateResponseSchema(ResponseSchema):
    """팀 재활성화 응답"""
    id: int
    object: Literal["team"] = "team"
    reactivated: bool = True


# ─────────────────────────────────────────────────────────
# ▼ 팀 멤버 작업 응답 스키마 (Stripe 스타일)
# ─────────────────────────────────────────────────────────
class TeamMemberInviteResponseSchema(ResponseSchema):
    """멤버 초대 응답"""
    team_id: int
    user_id: int
    object: Literal["team_member"] = "team_member"
    invited: bool = True
    permission_group_id: Optional[int] = None


class TeamMemberRemoveResponseSchema(ResponseSchema):
    """멤버 제거/탈퇴 응답"""
    team_id: int
    user_id: int
    object: Literal["team_member"] = "team_member"
    removed: bool = True


class TeamMemberPermissionResponseSchema(ResponseSchema):
    """멤버 권한 그룹 변경 응답"""
    team_id: int
    user_id: int
    object: Literal["team_member"] = "team_member"
    updated: bool = True
    permission_group_id: Optional[int] = None  # 변경된 권한 그룹 ID


# ─────────────────────────────────────────────────────────
# ▼ 온보딩 응답 스키마
# ─────────────────────────────────────────────────────────
class OnboardingUpdateResponseSchema(ResponseSchema):
    """온보딩 상태 업데이트 응답"""
    id: int
    object: Literal["team"] = "team"
    updated: bool = True
    onboarding_step1_done: bool
    onboarding_step2_done: bool
    onboarding_step3_done: bool
    onboarding_completed: bool


# ─────────────────────────────────────────────────────────
# ▼ 팀 설정 업데이트 응답
# ─────────────────────────────────────────────────────────
class TeamSettingsUpdateResponseSchema(ResponseSchema):
    """팀 설정 업데이트 응답"""
    id: int
    object: Literal["team"] = "team"
    updated: bool = True


# ─────────────────────────────────────────────────────────
# ▼ 팀 사용량 통계 응답
# ─────────────────────────────────────────────────────────
class TeamUsageStatsResponseSchema(ResponseSchema):
    """팀 사용량 통계 응답"""
    product_count: int
    product_limit: int
    member_count: int
    member_limit: int
    location_count: int
    location_limit: int


# ─────────────────────────────────────────────────────────
# ▼ 시간대 목록 응답
# ─────────────────────────────────────────────────────────
class TimezoneItemSchema(ResponseSchema):
    """시간대 목록 항목"""
    code: str   # IANA 시간대 ID (예: "Asia/Seoul")
    label: str  # 표시용 텍스트 (예: "(GMT+09:00) Asia/Seoul")