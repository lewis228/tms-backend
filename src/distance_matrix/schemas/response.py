# src/distance_matrix/schemas/response.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from common.schemas.base import ResponseSchema
from leg.const.status import DistanceProvider


class DistanceMatrixResponseSchema(ResponseSchema):
    id: int
    origin_location_id: int
    destination_location_id: int
    distance_value: Decimal
    duration_min: Decimal
    source: DistanceProvider
    measured_at: datetime | None = None
    note: str | None = None
    is_active: bool
