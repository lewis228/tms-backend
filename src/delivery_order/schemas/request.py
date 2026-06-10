# src/delivery_order/schemas/request.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal, List
from pydantic import Field, field_validator
from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from delivery_order.const.status import (
    DeliveryStatus, ShipmentDirection,
)
from container.schemas.request import ContainerCreateInner


class DeliveryOrderCreateRequest(RequestSchema):
    direction: ShipmentDirection
    customer_id: int
    bl_number: str | None = Field(default=None, max_length=64)
    booking_number: str | None = Field(default=None, max_length=64)
    reference: str | None = Field(default=None, max_length=120)
    terminal_id: int | None = None
    vessel_id: int | None = None
    eta: datetime | None = None
    bl_released: bool = False
    internal_note: str | None = Field(default=None, max_length=3000)

    # 컨테이너 nested — 비어있으면 빈 D/O 로 생성, 그렇지 않으면 N개 컨테이너 동시 생성
    containers: List[ContainerCreateInner] = Field(default_factory=list)


class DeliveryOrderUpdateRequest(RequestSchema):
    bl_number: str | None = Field(default=None, max_length=64)
    booking_number: str | None = Field(default=None, max_length=64)
    reference: str | None = Field(default=None, max_length=120)
    terminal_id: int | None = None
    vessel_id: int | None = None
    eta: datetime | None = None
    bl_released: bool | None = None
    internal_note: str | None = Field(default=None, max_length=3000)


class DeliveryOrderTransitionRequest(RequestSchema):
    """D/O 상태 전이 — service 가 게이트 검증."""
    target: DeliveryStatus


class DeliveryOrderHoldRequest(RequestSchema):
    """Hold 설정/해제."""
    on_hold: bool = True
    reason: str | None = Field(default=None, max_length=500)


class DeliveryOrderCancelRequest(RequestSchema):
    """D/O 취소."""
    reason: str | None = Field(default=None, max_length=500)


class PaginateDeliveryOrderRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__status__equal: Optional[DeliveryStatus] = None
    where__direction__equal: Optional[ShipmentDirection] = None
    where__customer_id__equal: Optional[int] = None
    where__bl_number__i_like: Optional[str] = None


class DeliveryOrderBulkCreateRequest(RequestSchema):
    items: List[DeliveryOrderCreateRequest] = Field(..., min_length=1, max_length=100)


class DeliveryOrderBulkUpdateItem(DeliveryOrderUpdateRequest):
    id: int


class DeliveryOrderBulkUpdateRequest(RequestSchema):
    items: List[DeliveryOrderBulkUpdateItem] = Field(..., min_length=1, max_length=100)


class DeliveryOrderBulkDeleteRequest(RequestSchema):
    ids: List[int] = Field(..., min_length=1, max_length=100)

    @field_validator('ids')
    @classmethod
    def unique_ids(cls, v: List[int]) -> List[int]:
        return list(dict.fromkeys(v))


# ── D/O 단위 Add-on (고객 청구용) ─────────────────────────────
class DoAddonCreateRequest(RequestSchema):
    delivery_order_id: int
    addon_id: int   # addon 마스터 타입
    quantity: Decimal = Decimal("1")
    unit_amount: Decimal | None = None
    amount: Decimal | None = None        # None 이면 시스템이 마스터 단가로 자동 채움
    note: str | None = Field(default=None, max_length=300)


class DoAddonUpdateRequest(RequestSchema):
    quantity: Decimal | None = None
    unit_amount: Decimal | None = None
    amount: Decimal | None = None
    note: str | None = Field(default=None, max_length=300)
