# src/rate_tariff/schemas/request.py
from __future__ import annotations
from datetime import date
from decimal import Decimal

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from container.const.status import ContainerSize
from leg.const.status import MoveTypeV3


class RateTariffCreateRequest(RequestSchema):
    name: str
    move_type: MoveTypeV3 | None = None
    container_size: ContainerSize | None = None
    customer_id: int | None = None
    per_value: Decimal = Decimal("0")
    per_min:   Decimal = Decimal("0")
    flat_base: Decimal = Decimal("0")
    effective_from: date
    effective_to: date | None = None
    priority: int = 0
    description: str | None = None


class RateTariffUpdateRequest(RequestSchema):
    name: str | None = None
    move_type: MoveTypeV3 | None = None
    container_size: ContainerSize | None = None
    customer_id: int | None = None
    per_value: Decimal | None = None
    per_min:   Decimal | None = None
    flat_base: Decimal | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    priority: int | None = None
    description: str | None = None


class PaginateRateTariffRequest(BasePaginationSchema):
    where__move_type__equal: MoveTypeV3 | None = None
    where__customer_id__equal: int | None = None
    include_inactive: bool = False
