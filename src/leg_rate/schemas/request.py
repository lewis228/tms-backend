# src/leg_rate/schemas/request.py
from __future__ import annotations
from decimal import Decimal

from common.schemas.base import RequestSchema


class LegRateUpdateRequest(RequestSchema):
    """디스패처가 leg_rate 를 수동 override 할 때.

    base_amount 를 직접 입력하면 manual_override=True. snapshot 컬럼들은 그대로 보존.
    """
    base_amount: Decimal | None = None
    payee_driver_id: int | None = None
    note: str | None = None


class RateCalculateRequest(RequestSchema):
    """leg 에 대한 base_amount 계산 — RateQuote 우선, RateTariff fallback.

    실제 leg 가 없는 견적 시뮬레이션에도 사용 가능.
    """
    leg_id: int | None = None  # 있으면 leg_rate 에 snapshot 박음
    origin_location_id: int | None = None
    destination_location_id: int | None = None
    container_size: str | None = None  # ContainerSize enum value
    move_type: str | None = None       # MoveTypeV3 enum value
    customer_id: int | None = None
