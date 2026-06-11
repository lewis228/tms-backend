# src/service_area/schemas/response.py
from __future__ import annotations
from typing import Literal

from common.schemas.base import ResponseSchema
from service_area.const.status import ServiceAreaKind


class ServiceAreaResponseSchema(ResponseSchema):
    id: int
    kind: ServiceAreaKind
    state: str
    value: str
    is_active: bool


class ServiceAreaDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["service_area"] = "service_area"
    deleted: bool = True
    soft_deleted: bool = False
