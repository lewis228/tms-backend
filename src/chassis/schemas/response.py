# src/chassis/schemas/response.py
from __future__ import annotations
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from chassis.const.status import ChassisOwnerKind, ChassisSize, ChassisStatus


class ChassisResponseSchema(ResponseSchema):
    id: int
    chassis_number: str
    size: ChassisSize | None = None
    owner_kind: ChassisOwnerKind
    owner_driver_id: int | None = None
    owner_pool_id: int | None = None
    status: ChassisStatus
    current_location_id: int | None = None
    note: str | None = None
    is_active: bool


class ChassisDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["chassis"] = "chassis"
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


class ChassisBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
