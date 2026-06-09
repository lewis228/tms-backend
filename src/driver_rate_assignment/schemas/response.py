# src/driver_rate_assignment/schemas/response.py
from __future__ import annotations
from datetime import date
from typing import Literal

from common.schemas.base import ResponseSchema


class DriverRateAssignmentResponseSchema(ResponseSchema):
    """Driver Rate Assignment 단건/목록 공용 응답."""
    id: int
    driver_id: int
    rate_group_id: int
    effective_from: date
    effective_to: date | None = None
    note: str | None = None
    is_active: bool


class DriverRateAssignmentDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["driver_rate_assignment"] = "driver_rate_assignment"
    deleted: bool = True
    soft_deleted: bool = False
