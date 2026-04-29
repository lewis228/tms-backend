# src/rate_quote/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from container.const.status import ContainerSize
from leg.const.status import MoveTypeV3


class RateQuoteCreateRequest(RequestSchema):
    name: str | None = None
    origin_location_id: int | None = None
    destination_location_id: int | None = None
    container_size: ContainerSize | None = None
    move_type: MoveTypeV3 | None = None
    customer_id: int | None = None
    fixed_amount: Decimal
    effective_from: date
    effective_to: date | None = None
    priority: int = 0
    description: str | None = None


class RateQuoteUpdateRequest(RequestSchema):
    name: str | None = None
    origin_location_id: int | None = None
    destination_location_id: int | None = None
    container_size: ContainerSize | None = None
    move_type: MoveTypeV3 | None = None
    customer_id: int | None = None
    fixed_amount: Decimal | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    priority: int | None = None
    description: str | None = None


class PaginateRateQuoteRequest(BasePaginationSchema):
    where__customer_id__equal: int | None = None
    where__origin_location_id__equal: int | None = None
    where__destination_location_id__equal: int | None = None
    include_inactive: bool = False
