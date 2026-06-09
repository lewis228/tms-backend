# src/rate_multiplier/schemas/request.py
from __future__ import annotations
from decimal import Decimal
from typing import Optional
from pydantic import Field

from common.schemas.base import RequestSchema
from rate_sheet.const.status import RateContainerSize


class RateMultiplierUpsertRequest(RequestSchema):
    """배율 등록/수정 (scope+size 단위 upsert)."""
    container_size: RateContainerSize
    rate_group_id: int | None = None  # None = 팀 전역
    factor: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=300)


class RateMultiplierListQuery(RequestSchema):
    rate_group_id: Optional[int] = None
    include_inactive: bool = False
