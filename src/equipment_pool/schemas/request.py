# src/equipment_pool/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from equipment_pool.const.status import EquipmentPoolKind


class EquipmentPoolCreateRequest(RequestSchema):
    name: str = Field(min_length=1, max_length=200)
    kind: EquipmentPoolKind
    operator: str | None = Field(default=None, max_length=200)
    location_id: int | None = None
    contact: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=3000)


class EquipmentPoolUpdateRequest(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: EquipmentPoolKind | None = None
    operator: str | None = Field(default=None, max_length=200)
    location_id: int | None = None
    contact: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=3000)


class PaginateEquipmentPoolRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__name__i_like: Optional[str] = None
    where__kind__equal: Optional[EquipmentPoolKind] = None


class EquipmentPoolBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
