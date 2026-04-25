"""Legs 라우터."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.legs.repository import LegRepository
from app.domains.legs.schema import (
    LegCreateRequest,
    LegResponse,
    LegStatusTransitionRequest,
    LegUpdateRequest,
)
from app.domains.legs.service import LegService

router = APIRouter(
    prefix="/api/v1/legs",
    tags=["legs"],
    dependencies=[require_min_role("DISPATCHER")],
)


def _svc(db, *, tenant_id: str) -> LegService:
    return LegService(LegRepository(db, tenant_id=tenant_id), tenant_id)


@router.get("", response_model=PagedResponse[LegResponse])
async def list_legs(
    tenant_id: TenantID,
    db: DBReadOnly,
    params: Annotated[PageParams, Depends(page_params)],
    delivery_order_id: str | None = Query(None, alias="deliveryOrderId"),
):
    if delivery_order_id:
        items = await _svc(db, tenant_id=tenant_id).list_for_delivery_order(delivery_order_id)
        return PagedResponse.of(
            [LegResponse.model_validate(i) for i in items], len(items), params
        )
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params)
    return PagedResponse.of([LegResponse.model_validate(i) for i in items], total, params)


@router.get("/{id}", response_model=LegResponse)
async def get_leg(id: str, tenant_id: TenantID, db: DBReadOnly):
    return LegResponse.model_validate(await _svc(db, tenant_id=tenant_id).get(id))


@router.post("", response_model=LegResponse, status_code=201)
async def create_leg(payload: LegCreateRequest, tenant_id: TenantID, db: DB):
    return LegResponse.model_validate(await _svc(db, tenant_id=tenant_id).create(payload))


@router.patch("/{id}", response_model=LegResponse)
async def update_leg(id: str, payload: LegUpdateRequest, tenant_id: TenantID, db: DB):
    return LegResponse.model_validate(await _svc(db, tenant_id=tenant_id).update(id, payload))


@router.post("/{id}/transition", response_model=LegResponse)
async def transition_leg(
    id: str, payload: LegStatusTransitionRequest, tenant_id: TenantID, db: DB
):
    return LegResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).transition(
            id, payload.target, failure_reason=payload.failure_reason
        )
    )


@router.delete("/{id}", status_code=204)
async def delete_leg(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
