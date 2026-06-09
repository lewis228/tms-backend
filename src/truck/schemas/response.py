# src/truck/schemas/response.py
from __future__ import annotations
from datetime import date
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from truck.const.status import TruckOwnerKind, TruckStatus


class TruckResponseSchema(ResponseSchema):
    id: int
    plate_no: str
    vin: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    owner_kind: TruckOwnerKind
    owner_driver_id: int | None = None
    status: TruckStatus
    registration_expires_at: date | None = None
    insurance_expires_at: date | None = None
    inspection_expires_at: date | None = None
    note: str | None = None
    is_active: bool


class TruckDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["truck"] = "truck"
    deleted: bool = True
    soft_deleted: bool = False


class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class TruckBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
