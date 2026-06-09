# src/truck/schemas/request.py
from __future__ import annotations
from datetime import date
from typing import Optional, Literal, List
from pydantic import Field, field_validator, model_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from truck.const.status import TruckOwnerKind, TruckStatus


class TruckCreateRequest(RequestSchema):
    plate_no: str = Field(min_length=1, max_length=32)
    vin: str | None = Field(default=None, max_length=32)
    make: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=64)
    year: int | None = None
    owner_kind: TruckOwnerKind = TruckOwnerKind.COMPANY
    owner_driver_id: int | None = None
    status: TruckStatus = TruckStatus.ACTIVE
    registration_expires_at: date | None = None
    insurance_expires_at: date | None = None
    inspection_expires_at: date | None = None
    note: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def _validate_owner(self):
        if self.owner_kind == TruckOwnerKind.DRIVER and not self.owner_driver_id:
            raise ValueError("owner_driver_id is required when owner_kind=DRIVER")
        if self.owner_kind == TruckOwnerKind.COMPANY and self.owner_driver_id:
            raise ValueError("owner_driver_id must be null when owner_kind=COMPANY")
        return self


class TruckUpdateRequest(RequestSchema):
    plate_no: str | None = Field(default=None, min_length=1, max_length=32)
    vin: str | None = Field(default=None, max_length=32)
    make: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=64)
    year: int | None = None
    owner_kind: TruckOwnerKind | None = None
    owner_driver_id: int | None = None
    status: TruckStatus | None = None
    registration_expires_at: date | None = None
    insurance_expires_at: date | None = None
    inspection_expires_at: date | None = None
    note: str | None = Field(default=None, max_length=3000)


class PaginateTruckRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'
    include_inactive: bool = False
    where__plate_no__i_like: Optional[str] = None
    where__owner_kind__equal: Optional[TruckOwnerKind] = None
    where__owner_driver_id__equal: Optional[int] = None
    where__status__equal: Optional[TruckStatus] = None


class TruckBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))
