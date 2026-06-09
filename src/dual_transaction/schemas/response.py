# src/dual_transaction/schemas/response.py
from __future__ import annotations
from datetime import datetime
from typing import Literal

from common.schemas.base import ResponseSchema
from dual_transaction.const.status import DualTransactionStatus


class DualTransactionResponseSchema(ResponseSchema):
    id: int
    driver_id: int
    truck_id: int | None = None
    return_leg_id: int
    pickup_leg_id: int
    status: DualTransactionStatus
    scheduled_at: datetime | None = None
    note: str | None = None
    is_active: bool


class DualTransactionDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["dual_transaction"] = "dual_transaction"
    deleted: bool = True
    soft_deleted: bool = False
