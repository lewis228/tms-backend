# src/chassis/schemas/request.py
from __future__ import annotations
from datetime import date
from typing import Optional, Literal, List
from pydantic import Field, field_validator, model_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from chassis.const.status import ChassisOwnerKind, ChassisSize, ChassisStatus


class ChassisCreateRequest(RequestSchema):
    chassis_number: str = Field(min_length=1, max_length=32)
    size: ChassisSize | None = None
    owner_kind: ChassisOwnerKind = ChassisOwnerKind.COMPANY
    owner_driver_id: int | None = None
    owner_pool_id: int | None = None
    status: ChassisStatus = ChassisStatus.AVAILABLE
    current_location_id: int | None = None
    registration_expires_at: date | None = None
    inspection_expires_at: date | None = None
    note: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def _validate_owner(self):
        if self.owner_kind == ChassisOwnerKind.DRIVER and not self.owner_driver_id:
            raise ValueError("owner_driver_id is required when owner_kind=DRIVER")
        if self.owner_kind in (ChassisOwnerKind.TERMINAL_POOL, ChassisOwnerKind.THIRD_PARTY_POOL) and not self.owner_pool_id:
            raise ValueError("owner_pool_id is required when owner_kind is a POOL")
        if self.owner_kind == ChassisOwnerKind.COMPANY and (self.owner_driver_id or self.owner_pool_id):
            raise ValueError("COMPANY owner must not have owner_driver_id or owner_pool_id")
        return self


class ChassisUpdateRequest(RequestSchema):
    chassis_number: str | None = Field(default=None, min_length=1, max_length=32)
    size: ChassisSize | None = None
    owner_kind: ChassisOwnerKind | None = None
    owner_driver_id: int | None = None
    owner_pool_id: int | None = None
    status: ChassisStatus | None = None
    current_location_id: int | None = None
    registration_expires_at: date | None = None
    inspection_expires_at: date | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateChassisRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__chassis_number__i_like: Optional[str] = None
    where__owner_kind__equal: Optional[ChassisOwnerKind] = None
    where__owner_driver_id__equal: Optional[int] = None
    where__owner_pool_id__equal: Optional[int] = None
    where__status__equal: Optional[ChassisStatus] = None


class ChassisBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
