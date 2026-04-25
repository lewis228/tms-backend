"""StreetTurns 라우터."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.delivery_orders.repository import DeliveryOrderRepository
from app.domains.street_turns.repository import StreetTurnRepository
from app.domains.street_turns.schema import (
    StreetTurnCreateRequest,
    StreetTurnResponse,
)
from app.domains.street_turns.service import StreetTurnService

router = APIRouter(
    prefix="/api/v1/street-turns",
    tags=["street-turns"],
    dependencies=[require_min_role("DISPATCHER")],
)


def _svc(db, *, tenant_id: str) -> StreetTurnService:
    return StreetTurnService(
        StreetTurnRepository(db, tenant_id=tenant_id),
        DeliveryOrderRepository(db, tenant_id=tenant_id),
        tenant_id,
    )


@router.get("", response_model=PagedResponse[StreetTurnResponse])
async def list_street_turns(
    tenant_id: TenantID, db: DBReadOnly, params: Annotated[PageParams, Depends(page_params)]
):
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params)
    return PagedResponse.of(
        [StreetTurnResponse.model_validate(i) for i in items], total, params
    )


@router.get("/{id}", response_model=StreetTurnResponse)
async def get_street_turn(id: str, tenant_id: TenantID, db: DBReadOnly):
    return StreetTurnResponse.model_validate(await _svc(db, tenant_id=tenant_id).get(id))


@router.post("", response_model=StreetTurnResponse, status_code=201)
async def create_street_turn(
    payload: StreetTurnCreateRequest, tenant_id: TenantID, db: DB
):
    return StreetTurnResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).create(payload)
    )


@router.delete("/{id}", status_code=204)
async def delete_street_turn(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
