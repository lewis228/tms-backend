"""Vessels 라우터."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.vessels.repository import VesselRepository
from app.domains.vessels.schema import (
    VesselCreateRequest,
    VesselResponse,
    VesselUpdateRequest,
)
from app.domains.vessels.service import VesselService

router = APIRouter(
    prefix="/api/v1/vessels",
    tags=["vessels"],
    dependencies=[require_min_role("DISPATCHER")],
)


def _svc(db, *, tenant_id: str) -> VesselService:
    return VesselService(VesselRepository(db, tenant_id=tenant_id), tenant_id)


@router.get("", response_model=PagedResponse[VesselResponse])
async def list_vessels(
    tenant_id: TenantID,
    db: DBReadOnly,
    params: Annotated[PageParams, Depends(page_params)],
    q: str | None = Query(None, description="이름 또는 IMO 번호 부분 일치", max_length=100),
):
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params, q=q)
    return PagedResponse.of([VesselResponse.model_validate(i) for i in items], total, params)


@router.get("/{id}", response_model=VesselResponse)
async def get_vessel(id: str, tenant_id: TenantID, db: DBReadOnly):
    return VesselResponse.model_validate(await _svc(db, tenant_id=tenant_id).get(id))


@router.post("", response_model=VesselResponse, status_code=201)
async def create_vessel(payload: VesselCreateRequest, tenant_id: TenantID, db: DB):
    return VesselResponse.model_validate(await _svc(db, tenant_id=tenant_id).create(payload))


@router.patch("/{id}", response_model=VesselResponse)
async def update_vessel(id: str, payload: VesselUpdateRequest, tenant_id: TenantID, db: DB):
    return VesselResponse.model_validate(await _svc(db, tenant_id=tenant_id).update(id, payload))


@router.delete("/{id}", status_code=204)
async def delete_vessel(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
