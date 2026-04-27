# src/team/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class TeamCreateRequestSchema(RequestSchema):
    """팀 생성 요청 바디"""
    name: str = Field(min_length=1, description="팀 이름")


class TeamRenameRequestSchema(RequestSchema):
    """팀 이름 변경 요청 바디"""
    name: str = Field(min_length=1, description="새 팀 이름")


class InviteMemberRequestSchema(RequestSchema):
    """팀 멤버 초대 요청 바디"""
    user_id: int
    permission_group_id: Optional[int] = None


class AssignPermissionGroupRequestSchema(RequestSchema):
    """팀 멤버 권한 그룹 지정 요청 바디"""
    permission_group_id: Optional[int] = None


# ─────────────────────────────────────────────────────────
# ▼ 커서 페이지네이션 요청
#   - 공통 BasePaginationSchema 상속
#   - 기본 정렬: id ASC (먼저 생성된 팀 우선)
#   - 선택 필터: 팀 이름 부분검색(선택, 대소문자 무시 i_like)
# ─────────────────────────────────────────────────────────
class PaginateTeamRequestSchema(BasePaginationSchema):
    # 예) ?where__name__i_like=첫&order__id=DESC&take=20
    where__name__i_like: Optional[str] = None
    #  Literal로 허용값 고정 → 잘못된 값 즉시 400 방지
    order__name: Optional[Literal["ASC", "DESC"]] = None


class PaginateTeamMemberRequestSchema(BasePaginationSchema):
    """
    팀 멤버 목록 커서 페이지네이션 요청
    - CommonService + FILTER_MAPPER 규칙 그대로 사용
    - BasePaginationSchema 상속으로 커서 키, take, order__id 등 자동 포함
    """
    # 정렬 추가 가능 (기본 order__id는 상속됨)
    order__user_id: Optional[Literal["ASC", "DESC"]] = None
    order__permission_group_id: Optional[Literal["ASC", "DESC"]] = None

    # 팀 멤버 전용 필터
    where__user_id__equal: Optional[int] = None
    where__permission_group_id__equal: Optional[int] = None


class OnboardingUpdateRequestSchema(RequestSchema):
    """온보딩 상태 업데이트 요청 바디"""
    step1_done: Optional[bool] = None
    step2_done: Optional[bool] = None
    step3_done: Optional[bool] = None
    completed: Optional[bool] = None


class TeamSettingsUpdateRequestSchema(RequestSchema):
    """팀 설정 업데이트 요청 바디 (PATCH — 전달된 필드만 업데이트)"""
    # 팀 정보
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    memo: Optional[str] = Field(None, max_length=3000)
    timezone: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=500)

    # 파일 관리 (이미지 업로드/삭제)
    temp_keys: Optional[List[str]] = None
    remove_file_ids: Optional[List[int]] = None

    # 회사 정보
    company_name: Optional[str] = Field(None, max_length=120)
    registration_number: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=500)
    representative_name: Optional[str] = Field(None, max_length=80)
    phone_number: Optional[str] = Field(None, max_length=30)

    # 표시 설정
    currency: Optional[str] = Field(None, max_length=10)
    decimal_places: Optional[int] = Field(None, ge=0, le=3)
    product_info_display: Optional[str] = Field(None, max_length=30)
    product_info_template: Optional[str] = Field(None, max_length=500)

    # 엑셀 가져오기
    excel_product_identification: Optional[str] = Field(None, max_length=30)

    # 바코드 스캔
    gs1_gtin_enabled: Optional[bool] = None
