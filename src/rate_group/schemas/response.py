# src/rate_group/schemas/response.py
from __future__ import annotations
from typing import Literal

from common.schemas.base import ResponseSchema
from rate_group.const.status import RateMethod


class RateGroupResponseSchema(ResponseSchema):
    """Rate Group 단건/목록 공용 응답."""
    id: int
    name: str
    method: RateMethod
    is_default: bool
    is_template: bool
    description: str | None = None
    is_active: bool


class RateGroupDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["rate_group"] = "rate_group"
    deleted: bool = True
    soft_deleted: bool = False
