# src/rate_zone/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema


class RateZoneMemberItem(RequestSchema):
    """Zone 멤버 입력 항목. 존 = zip 묶음이므로 zip_code 필수."""
    zip_code: str = Field(min_length=1, max_length=16)


class RateZoneCreateRequest(RequestSchema):
    """Rate Zone 생성 DTO (멤버 인라인 동시 생성 허용)."""
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=16)
    geojson: dict | None = None
    description: str | None = Field(default=None, max_length=3000)
    members: List[RateZoneMemberItem] = Field(default_factory=list, max_length=5000)


class RateZoneUpdateRequest(RequestSchema):
    """Rate Zone 헤더 수정 DTO (멤버는 /members 로 별도 관리)."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=16)
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
