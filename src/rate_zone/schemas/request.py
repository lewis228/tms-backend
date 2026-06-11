# src/rate_zone/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field, model_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class RateZoneMemberItem(RequestSchema):
    """Zone 멤버 입력 항목 — zip 1개 XOR (city,state) 1쌍.

    ZIP 방식 존은 zip 멤버, CITY 방식 도시존은 city 멤버.
    """
    zip_code: str | None = Field(default=None, min_length=1, max_length=16)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    state: str | None = Field(default=None, max_length=8)

    @model_validator(mode="after")
    def _validate_atom(self):
        if bool(self.zip_code) == bool(self.city):
            raise ValueError("멤버는 zip_code 또는 (city,state) 중 정확히 하나여야 합니다.")
        if self.city and not self.state:
            raise ValueError("city 멤버는 state 가 필요합니다 (도시명 비유일).")
        if self.zip_code and self.state:
            raise ValueError("zip 멤버에는 state 를 지정하지 않습니다.")
        return self


class RateZoneCreateRequest(RequestSchema):
    """Rate Zone 생성 DTO (멤버 인라인 동시 생성 허용).

    rate_group_id=None 이면 팀 공용(글로벌) 존, 값이 있으면 그 그룹 전용 존.
    """
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=16)
    rate_group_id: int | None = None
    geojson: dict | None = None
    description: str | None = Field(default=None, max_length=3000)
    members: List[RateZoneMemberItem] = Field(default_factory=list, max_length=5000)


class RateZoneUpdateRequest(RequestSchema):
    """Rate Zone 헤더 수정 DTO (멤버는 /members 로 별도 관리)."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=16)
    rate_group_id: int | None = None  # 스코프 변경 (None 전달 시 무시 — 글로벌화는 미지원)
    geojson: dict | None = None
    description: str | None = Field(default=None, max_length=3000)


class RateZoneMembersReplaceRequest(RequestSchema):
    """Zone 의 멤버 전체 교체 (PUT 시맨틱)."""
    members: List[RateZoneMemberItem] = Field(default_factory=list, max_length=5000)


class AddMembersByCityRequest(RequestSchema):
    """(city, state) 의 모든 zip 을 멤버로 합집합 추가. 도시명 비유일 → state 필수."""
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=2, max_length=8)


class PaginateRateZoneRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'

    include_inactive: bool = False

    where__name__i_like: Optional[str] = None
    where__code__i_like: Optional[str] = None
    where__rate_group_id__equal: Optional[int] = None
