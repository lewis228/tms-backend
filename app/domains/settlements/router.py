"""Settlements 라우터 — DISPATCHER+ (조회/계산/수정), ADMIN+ (Unapprove)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import (
    CurrentUser,
    DB,
    DBReadOnly,
    TenantID,
    require_min_role,
)
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.settlements.repository import SettlementRepository
from app.domains.settlements.schema import (
    AuditLogResponse,
    ExtraChargeResponse,
    SettlementAdjustRequest,
    SettlementApproveRequest,
    SettlementCalculateRequest,
    SettlementResponse,
    SettlementUnapproveRequest,
)
from app.domains.settlements.service import SettlementService

router = APIRouter(prefix="/api/v1/settlements", tags=["settlements"])


def _svc(db, *, tenant_id: str) -> SettlementService:
    return SettlementService(SettlementRepository(db, tenant_id=tenant_id), tenant_id)


@router.get(
    "",
    response_model=PagedResponse[SettlementResponse],
    dependencies=[require_min_role("DISPATCHER")],
)
async def list_settlements(
    tenant_id: TenantID, db: DBReadOnly, params: Annotated[PageParams, Depends(page_params)]
):
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params)
    return PagedResponse.of(
        [SettlementResponse.model_validate(i) for i in items], total, params
    )


@router.get(
    "/{id}",
    response_model=SettlementResponse,
    dependencies=[require_min_role("DISPATCHER")],
)
async def get_settlement(id: str, tenant_id: TenantID, db: DBReadOnly):
    return SettlementResponse.model_validate(await _svc(db, tenant_id=tenant_id).get(id))


@router.get(
    "/{id}/extras",
    response_model=list[ExtraChargeResponse],
    dependencies=[require_min_role("DISPATCHER")],
)
async def list_extras(id: str, tenant_id: TenantID, db: DBReadOnly):
    _, extras = await _svc(db, tenant_id=tenant_id).get_with_extras(id)
    return [ExtraChargeResponse.model_validate(e) for e in extras]


@router.get(
    "/{id}/audit-logs",
    response_model=list[AuditLogResponse],
    dependencies=[require_min_role("DISPATCHER")],
)
async def list_audit_logs(id: str, tenant_id: TenantID, db: DBReadOnly):
    logs = await _svc(db, tenant_id=tenant_id).list_audit_logs(id)
    return [AuditLogResponse.model_validate(l) for l in logs]


@router.post(
    "/{id}/calculate",
    response_model=SettlementResponse,
    dependencies=[require_min_role("DISPATCHER")],
)
async def calculate(
    id: str,
    payload: SettlementCalculateRequest,
    user: CurrentUser,
    tenant_id: TenantID,
    db: DB,
):
    return SettlementResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).calculate(id, payload, actor_id=user.user_id)
    )


@router.post(
    "/{id}/adjust",
    response_model=SettlementResponse,
    dependencies=[require_min_role("DISPATCHER")],
)
async def adjust(
    id: str,
    payload: SettlementAdjustRequest,
    user: CurrentUser,
    tenant_id: TenantID,
    db: DB,
):
    return SettlementResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).adjust(id, payload, actor_id=user.user_id)
    )


@router.post(
    "/{id}/approve",
    response_model=SettlementResponse,
    dependencies=[require_min_role("DISPATCHER")],
)
async def approve(
    id: str,
    payload: SettlementApproveRequest,
    user: CurrentUser,
    tenant_id: TenantID,
    db: DB,
):
    return SettlementResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).approve(id, payload, actor_id=user.user_id)
    )


@router.post(
    "/{id}/unapprove",
    response_model=SettlementResponse,
    dependencies=[require_min_role("ADMIN")],
)
async def unapprove(
    id: str,
    payload: SettlementUnapproveRequest,
    user: CurrentUser,
    tenant_id: TenantID,
    db: DB,
):
    return SettlementResponse.model_validate(
        await _svc(db, tenant_id=tenant_id).unapprove(id, payload, actor_id=user.user_id)
    )
