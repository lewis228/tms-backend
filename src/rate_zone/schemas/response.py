# src/rate_zone/schemas/response.py
from __future__ import annotations
from typing import Literal, List

from common.schemas.base import ResponseSchema


class RateZoneMemberResponseSchema(ResponseSchema):
    id: int
    zip_code: str | None = None
    city: str | None = None
    state: str | None = None


class RateZoneSummarySchema(ResponseSchema):
    """목록/sync 용 — members 미포함 (lazy='raise' 관계 접근 방지)."""
    id: int
    name: str
    code: str | None = None
    color: str | None = None
    geojson: dict | None = None
    description: str | None = None
    is_active: bool


class RateZoneResponseSchema(RateZoneSummarySchema):
    """상세 — members 포함 (selectinload 된 경우)."""
    members: List[RateZoneMemberResponseSchema] = []


class RateZoneDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["rate_zone"] = "rate_zone"
    deleted: bool = True
    soft_deleted: bool = False


class RateZoneMembersResponseSchema(ResponseSchema):
    """멤버 교체/조회 응답."""
    zone_id: int
    members: List[RateZoneMemberResponseSchema] = []
    count: int = 0
