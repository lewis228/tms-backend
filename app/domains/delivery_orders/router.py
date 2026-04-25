"""DeliveryOrders 라우터 — DISPATCHER+ CRUD + 상태 전이."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.delivery_orders.repository import DeliveryOrderRepository
from app.domains.delivery_orders.schema import (
    DeliveryOrderCreateRequest,
    DeliveryOrderResponse,
    DeliveryOrderUpdateRequest,
    StatusTransitionRequest,
)
from app.domains.delivery_orders.service import DeliveryOrderService

router = APIRouter(
    prefix="/api/v1/delivery-orders",
    tags=["delivery-orders"],
    dependencies=[require_min_role("DISPATCHER")],
)


def _svc(db, *, tenant_id: str) -> DeliveryOrderService:
    return DeliveryOrderService(
        DeliveryOrderRepository(db, tenant_id=tenant_id), tenant_id
    )


@router.get("", response_model=PagedResponse[DeliveryOrderResponse])
async def list_delivery_orders(
    tenant_id: TenantID, db: DBReadOnly, params: Annotated[PageParams, Depends(page_params)]
):
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params)
    return PagedResponse.of(
        [DeliveryOrderResponse.model_validate(i) for i in items], total, params
    )


@router.get("/{id}", response_model=DeliveryOrderResponse)
async def get_delivery_order(id: str, tenant_id: TenantID, db: DBReadOnly):
    return DeliveryOrderResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).get(id)
    )


@router.post("", response_model=DeliveryOrderResponse, status_code=201)
async def create_delivery_order(
    payload: DeliveryOrderCreateRequest, tenant_id: TenantID, db: DB
):
    return DeliveryOrderResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).create(payload)
    )


@router.patch("/{id}", response_model=DeliveryOrderResponse)
async def update_delivery_order(
    id: str, payload: DeliveryOrderUpdateRequest, tenant_id: TenantID, db: DB
):
    return DeliveryOrderResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).update(id, payload)
    )


@router.post("/{id}/transition", response_model=DeliveryOrderResponse)
async def transition_status(
    id: str, payload: StatusTransitionRequest, tenant_id: TenantID, db: DB
):
    return DeliveryOrderResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).transition(id, payload.target)
    )


@router.delete("/{id}", status_code=204)
async def delete_delivery_order(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
