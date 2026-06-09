# src/load_type_template/schemas/response.py
from __future__ import annotations
from typing import Literal, List

from common.schemas.base import ResponseSchema
from load_type_template.const.status import (
    LoadDirection, TemplateLocationType, TemplateMoveType, TemplateServiceType, TemplateMoveCode,
)


class TemplateStepResponseSchema(ResponseSchema):
    id: int
    seq: int
    from_location_type: TemplateLocationType | None = None
    to_location_type: TemplateLocationType | None = None
    move_type: TemplateMoveType
    service_type: TemplateServiceType
    move_code: TemplateMoveCode | None = None
    flags: dict | None = None
    note: str | None = None


class LoadTypeTemplateSummarySchema(ResponseSchema):
    """목록/sync 용 — steps 미포함 (lazy='raise' 관계 접근 방지)."""
    id: int
    code: str
    name: str
    direction: LoadDirection
    description: str | None = None
    is_system: bool
    is_active: bool


class LoadTypeTemplateResponseSchema(LoadTypeTemplateSummarySchema):
    """상세 — steps 포함 (selectinload 된 경우만 사용)."""
    steps: List[TemplateStepResponseSchema] = []


class LoadTypeTemplateDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["load_type_template"] = "load_type_template"
    deleted: bool = True
    soft_deleted: bool = False


class SeedDefaultsResponseSchema(ResponseSchema):
    created: int
    skipped: int
    total: int
