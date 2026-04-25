"""Tenants 라우터 — SUPER_ADMIN CRUD + 본인 GET /me."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.dependencies import CurrentUser, DB, DBReadOnly, require_role
from app.core.exceptions import ForbiddenError
from app.domains.tenants.repository import TenantRepository
from app.domains.tenants.schema import (
    TenantCreateRequest,
    TenantResponse,
    TenantUpdateRequest,
)
from app.domains.tenants.service import TenantService

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


def _svc(db) -> TenantService:
    return TenantService(TenantRepository(db))


@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(user: CurrentUser, db: DBReadOnly):
    if not user.tenant_id:
        raise ForbiddenError("User has no tenant", code="ERR_NO_TENANT")
    tenant = await _svc(db).get(user.tenant_id)
    return TenantResponse.model_validate(tenant)


@router.get(
    "",
    response_model=list[TenantResponse],
    dependencies=[require_role("SUPER_ADMIN")],
)
async def list_tenants(db: DBReadOnly):
    tenants = await _svc(db).list_all()
    return [TenantResponse.model_validate(t) for t in tenants]


@router.post(
    "",
    response_model=TenantResponse,
    status_code=201,
    dependencies=[require_role("SUPER_ADMIN")],
)
async def create_tenant(payload: TenantCreateRequest, db: DB):
    tenant = await _svc(db).create(payload)
    return TenantResponse.model_validate(tenant)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[require_role("SUPER_ADMIN")],
)
async def get_tenant(tenant_id: str, db: DBReadOnly):
    tenant = await _svc(db).get(tenant_id)
    return TenantResponse.model_validate(tenant)


@router.patch(
    "/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[require_role("SUPER_ADMIN")],
)
async def update_tenant(tenant_id: str, payload: TenantUpdateRequest, db: DB):
    tenant = await _svc(db).update(tenant_id, payload)
    return TenantResponse.model_validate(tenant)


@router.delete(
    "/{tenant_id}",
    status_code=204,
    dependencies=[require_role("SUPER_ADMIN")],
)
async def delete_tenant(tenant_id: str, db: DB):
    await _svc(db).delete(tenant_id)
