# src/analytics/schemas/response.py
"""H-9 Dashboard analytics 응답 스키마."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import List

from common.schemas.base import ResponseSchema


class MarginTrendPoint(ResponseSchema):
    bucket: date
    revenue: Decimal
    payouts: Decimal
    margin: Decimal


class MarginTrendResponse(ResponseSchema):
    days: int
    points: List[MarginTrendPoint]
    total_revenue: Decimal
    total_payouts: Decimal
    total_margin: Decimal


class DriverUtilizationRow(ResponseSchema):
    driver_id: int
    driver_name: str
    total_legs: int
    completed_legs: int
    in_transit_legs: int
    utilization_pct: float


class DriverUtilizationResponse(ResponseSchema):
    days: int
    rows: List[DriverUtilizationRow]


class ContainerTurnoverPoint(ResponseSchema):
    bucket: date
    picked: int
    returned: int
    street_turned: int


class ContainerTurnoverResponse(ResponseSchema):
    days: int
    points: List[ContainerTurnoverPoint]
    avg_dwell_days: float


class StreetTurnSavingsResponse(ResponseSchema):
    days: int
    approved_count: int
    requested_count: int
    rejected_count: int
    savings_amount: Decimal
    saving_per_turn: Decimal
