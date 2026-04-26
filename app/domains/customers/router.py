"""Customers 라우터 — 조회 DISPATCHER+, 수정 ADMIN+."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.customers.repository import CustomerRepository
from app.domains.customers.schema import (
    CustomerCreateRequest,
    CustomerResponse,
    CustomerUpdateRequest,
)
from app.domains.customers.service import CustomerService

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


def _svc(db, *, tenant_id: str) -> CustomerService:
    return CustomerService(CustomerRepository(db, tenant_id=tenant_id), tenant_id)


@router.get(
    "",
    response_model=PagedResponse[CustomerResponse],
    dependencies=[require_min_role("DISPATCHER")],
)
async def list_customers(
    tenant_id: TenantID,
    db: DBReadOnly,
    params: Annotated[PageParams, Depends(page_params)],
    q: str | None = Query(None, description="이름 또는 코드 부분 일치", max_length=100),
):
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params, q=q)
    return PagedResponse.of(
        [CustomerResponse.model_validate(i) for i in items], total, params
    )


@router.get(
    "/{id}",
    response_model=CustomerResponse,
    dependencies=[require_min_role("DISPATCHER")],
)
async def get_customer(id: str, tenant_id: TenantID, db: DBReadOnly):
    return CustomerResponse.model_validate(await _svc(db, tenant_id=tenant_id).get(id))


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=201,
    dependencies=[require_min_role("ADMIN")],
)
async def create_customer(payload: CustomerCreateRequest, tenant_id: TenantID, db: DB):
    return CustomerResponse.model_validate(await _svc(db, tenant_id=tenant_id).create(payload))


@router.patch(
    "/{id}",
    response_model=CustomerResponse,
    dependencies=[require_min_role("ADMIN")],
)
async def update_customer(
    id: str, payload: CustomerUpdateRequest, tenant_id: TenantID, db: DB
):
    return CustomerResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).update(id, payload)
    )


@router.delete(
    "/{id}", status_code=204, dependencies=[require_min_role("ADMIN")]
)
async def delete_customer(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
