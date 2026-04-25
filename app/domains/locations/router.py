"""Locations 라우터 — DISPATCHER+ CRUD."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.locations.repository import LocationRepository
from app.domains.locations.schema import (
    LocationCreateRequest,
    LocationResponse,
    LocationUpdateRequest,
)
from app.domains.locations.service import LocationService

router = APIRouter(
    prefix="/api/v1/locations",
    tags=["locations"],
    dependencies=[require_min_role("DISPATCHER")],
)


def _svc(db, *, tenant_id: str) -> LocationService:
    return LocationService(LocationRepository(db, tenant_id=tenant_id), tenant_id)


@router.get("", response_model=PagedResponse[LocationResponse])
async def list_locations(
    tenant_id: TenantID, db: DBReadOnly, params: Annotated[PageParams, Depends(page_params)]
):
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params)
    return PagedResponse.of([LocationResponse.model_validate(i) for i in items], total, params)


@router.get("/{id}", response_model=LocationResponse)
async def get_location(id: str, tenant_id: TenantID, db: DBReadOnly):
    return LocationResponse.model_validate(await _svc(db, tenant_id=tenant_id).get(id))


@router.post("", response_model=LocationResponse, status_code=201)
async def create_location(payload: LocationCreateRequest, tenant_id: TenantID, db: DB):
    return LocationResponse.model_validate(await _svc(db, tenant_id=tenant_id).create(payload))


@router.patch("/{id}", response_model=LocationResponse)
async def update_location(
    id: str, payload: LocationUpdateRequest, tenant_id: TenantID, db: DB
):
    return LocationResponse.model_validate(await _svc(db, tenant_id=tenant_id).update(id, payload))


@router.delete("/{id}", status_code=204)
async def delete_location(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
