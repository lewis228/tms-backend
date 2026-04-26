"""Drivers 라우터 — DISPATCHER+ CRUD."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.drivers.repository import DriverRepository
from app.domains.drivers.schema import (
    DriverCreatedResponse,
    DriverCreateRequest,
    DriverResponse,
    DriverUpdateRequest,
)
from app.domains.drivers.service import DriverService
from app.domains.users.repository import UserRepository

router = APIRouter(
    prefix="/api/v1/drivers",
    tags=["drivers"],
    dependencies=[require_min_role("DISPATCHER")],
)


def _svc(db, *, tenant_id: str) -> DriverService:
    return DriverService(
        DriverRepository(db, tenant_id=tenant_id),
        UserRepository(db, tenant_id=tenant_id),
        tenant_id,
    )


def _to_response(driver, user) -> DriverResponse:
    return DriverResponse(
        id=driver.id,
        tenant_id=driver.tenant_id,
        user_id=driver.user_id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        license_number=driver.license_number,
        license_state=driver.license_state,
        truck_number=driver.truck_number,
        is_active=driver.is_active,
        note=driver.note,
        created_at=driver.created_at,
        updated_at=driver.updated_at,
    )


@router.post("", response_model=DriverCreatedResponse, status_code=201)
async def create_driver(payload: DriverCreateRequest, tenant_id: TenantID, db: DB):
    driver, user, temp_pw = await _svc(db, tenant_id=tenant_id).create(payload)
    base = _to_response(driver, user).model_dump()
    return DriverCreatedResponse(**base, temp_password=temp_pw)


@router.get("", response_model=PagedResponse[DriverResponse])
async def list_drivers(
    tenant_id: TenantID,
    db: DBReadOnly,
    params: Annotated[PageParams, Depends(page_params)],
    active_only: bool = Query(False, alias="activeOnly"),
    q: str | None = Query(
        None,
        description="이름/이메일/전화/차량번호 부분 일치",
        max_length=100,
    ),
):
    drivers, users, total = await _svc(db, tenant_id=tenant_id).list_paged(
        params, active_only=active_only, q=q
    )
    items = [_to_response(d, users[d.user_id]) for d in drivers if d.user_id in users]
    return PagedResponse.of(items, total, params)


@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: str, tenant_id: TenantID, db: DBReadOnly):
    driver, user = await _svc(db, tenant_id=tenant_id).get(driver_id)
    return _to_response(driver, user)


@router.patch("/{driver_id}", response_model=DriverResponse)
async def update_driver(
    driver_id: str, payload: DriverUpdateRequest, tenant_id: TenantID, db: DB
):
    driver, user = await _svc(db, tenant_id=tenant_id).update(driver_id, payload)
    return _to_response(driver, user)


@router.delete("/{driver_id}", status_code=204)
async def delete_driver(driver_id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(driver_id)
