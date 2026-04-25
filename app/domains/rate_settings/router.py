"""RateSettings 라우터 — ADMIN+."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.rate_settings.repository import RateSettingRepository
from app.domains.rate_settings.schema import (
    RateSettingCreateRequest,
    RateSettingResponse,
    RateSettingUpdateRequest,
)
from app.domains.rate_settings.service import RateSettingService

router = APIRouter(
    prefix="/api/v1/rate-settings",
    tags=["rate-settings"],
    dependencies=[require_min_role("ADMIN")],
)


def _svc(db, *, tenant_id: str) -> RateSettingService:
    return RateSettingService(RateSettingRepository(db, tenant_id=tenant_id), tenant_id)


@router.get("", response_model=PagedResponse[RateSettingResponse])
async def list_rate_settings(
    tenant_id: TenantID, db: DBReadOnly, params: Annotated[PageParams, Depends(page_params)]
):
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params)
    return PagedResponse.of(
        [RateSettingResponse.model_validate(i) for i in items], total, params
    )


@router.get("/{id}", response_model=RateSettingResponse)
async def get_rate_setting(id: str, tenant_id: TenantID, db: DBReadOnly):
    return RateSettingResponse.model_validate(await _svc(db, tenant_id=tenant_id).get(id))


@router.post("", response_model=RateSettingResponse, status_code=201)
async def create_rate_setting(
    payload: RateSettingCreateRequest, tenant_id: TenantID, db: DB
):
    return RateSettingResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).create(payload)
    )


@router.patch("/{id}", response_model=RateSettingResponse)
async def update_rate_setting(
    id: str, payload: RateSettingUpdateRequest, tenant_id: TenantID, db: DB
):
    return RateSettingResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).update(id, payload)
    )


@router.delete("/{id}", status_code=204)
async def delete_rate_setting(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
