# src/user/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field
from common.pagination.schemas.pagination_request import BasePaginationSchema
from common.schemas.base import RequestSchema  

class PaginateUserRequestSchema(BasePaginationSchema):
    """
    사용자 목록 커서/페이지 페이지네이션 요청 DTO
    - BasePaginationSchema 상속: page/take, where__id__*, order__id 포함
    - 추가 정렬: order__email / order__created_at
    - 추가 필터: where__email__i_like (부분검색, 대소문자 무시), where__role__equal

     사용 예시
    - 기본(최신→과거): GET /user?take=20&order__id=DESC
    - 오래된 것부터:   GET /user?take=20&order__id=ASC
    - 이메일 검색:     GET /user?where__email__i_like=gmail
    - 역할 필터:       GET /user?where__role__equal=ADMIN
    - 다음 페이지(next): 서버가 내려준 meta.next 그대로 호출
    """
    # 정렬
    order__email: Optional[Literal["ASC", "DESC"]] = None
    order__created_at: Optional[Literal["ASC", "DESC"]] = None

    # 필터
    where__email__i_like: Optional[str] = Field(default=None, description="이메일 부분검색(대소문자 무시)")
    where__role__equal: Optional[str] = Field(default=None, description="역할(예: ADMIN/USER)")


# ─────────────────────────────────────────────
# 프로필 업데이트 요청
# ─────────────────────────────────────────────
class UserProfileUpdateRequest(RequestSchema):
    """
    사용자 프로필 업데이트 요청
    
    - name: 사용자 이름 (최대 100자)
    - phone: 전화번호 (최대 30자, 나중에 사용)
    - event_notification_enabled: 이벤트 알림 수신 여부
    - temp_keys: 새로 업로드한 이미지의 개별 키
    - remove_file_ids: 삭제할 기존 이미지 ID
    """
    name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)

    #  이벤트 알림 수신 여부
    event_notification_enabled: Optional[bool] = None

    #  언어 설정 (auto, ko, en, es, fr, pt, id, zh-CN, zh-TW, ja, de)
    language: Optional[str] = Field(None, max_length=10)

    temp_keys: List[str] = Field(default_factory=list)
    remove_file_ids: List[int] = Field(default_factory=list)