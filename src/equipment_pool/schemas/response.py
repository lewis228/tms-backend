# src/equipment_pool/schemas/response.py
from __future__ import annotations
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from equipment_pool.const.status import EquipmentPoolKind


class EquipmentPoolResponseSchema(ResponseSchema):
    id: int
    name: str
    kind: EquipmentPoolKind
    operator: str | None = None
    location_id: int | None = None
    contact: str | None = None
    note: str | None = None
    is_active: bool


class EquipmentPoolDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["equipment_pool"] = "equipment_pool"
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


class EquipmentPoolBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
