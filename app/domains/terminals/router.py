"""Terminals 라우터."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DB, DBReadOnly, TenantID, require_min_role
from app.core.pagination import PageParams, PagedResponse, page_params
from app.domains.terminals.repository import TerminalRepository
from app.domains.terminals.schema import (
    TerminalCreateRequest,
    TerminalResponse,
    TerminalUpdateRequest,
)
from app.domains.terminals.service import TerminalService

router = APIRouter(prefix="/api/v1/terminals", tags=["terminals"])


def _svc(db, *, tenant_id: str) -> TerminalService:
    return TerminalService(TerminalRepository(db, tenant_id=tenant_id), tenant_id)


@router.get(
    "",
    response_model=PagedResponse[TerminalResponse],
    dependencies=[require_min_role("DISPATCHER")],
)
async def list_terminals(
    tenant_id: TenantID, db: DBReadOnly, params: Annotated[PageParams, Depends(page_params)]
):
    items, total = await _svc(db, tenant_id=tenant_id).list_paged(params)
    return PagedResponse.of([TerminalResponse.model_validate(i) for i in items], total, params)


@router.get(
    "/{id}",
    response_model=TerminalResponse,
    dependencies=[require_min_role("DISPATCHER")],
)
async def get_terminal(id: str, tenant_id: TenantID, db: DBReadOnly):
    return TerminalResponse.model_validate(await _svc(db, tenant_id=tenant_id).get(id))


@router.post(
    "",
    response_model=TerminalResponse,
    status_code=201,
    dependencies=[require_min_role("ADMIN")],
)
async def create_terminal(payload: TerminalCreateRequest, tenant_id: TenantID, db: DB):
    return TerminalResponse.model_validate(await _svc(db, tenant_id=tenant_id).create(payload))


@router.patch(
    "/{id}",
    response_model=TerminalResponse,
    dependencies=[require_min_role("ADMIN")],
)
async def update_terminal(
    id: str, payload: TerminalUpdateRequest, tenant_id: TenantID, db: DB
):
    return TerminalResponse.model_validate(await _svc(db, tenant_id=tenant_id).update(id, payload))


@router.delete("/{id}", status_code=204, dependencies=[require_min_role("ADMIN")])
async def delete_terminal(id: str, tenant_id: TenantID, db: DB):
    await _svc(db, tenant_id=tenant_id).delete(id)
