# src/load_type_template/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from load_type_template.const.status import (
    LoadDirection, TemplateLocationType, TemplateMoveType, TemplateServiceType, TemplateMoveCode,
)


class TemplateStepItem(RequestSchema):
    seq: int = Field(ge=1)
    from_location_type: TemplateLocationType | None = None
    to_location_type: TemplateLocationType | None = None
    move_type: TemplateMoveType
    service_type: TemplateServiceType
    move_code: TemplateMoveCode | None = None
    flags: dict | None = None
    note: str | None = Field(default=None, max_length=300)


class LoadTypeTemplateCreateRequest(RequestSchema):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=120)
    direction: LoadDirection
    description: str | None = Field(default=None, max_length=3000)
    steps: List[TemplateStepItem] = Field(default_factory=list, max_length=20)


class LoadTypeTemplateUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    direction: LoadDirection | None = None
    description: str | None = Field(default=None, max_length=3000)


class TemplateStepsReplaceRequest(RequestSchema):
    steps: List[TemplateStepItem] = Field(default_factory=list, max_length=20)


class PaginateLoadTypeTemplateRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__direction__equal: Optional[LoadDirection] = None
    where__code__i_like: Optional[str] = None
    where__name__i_like: Optional[str] = None
