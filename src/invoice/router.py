# src/invoice/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import INVOICE_WRITE, INVOICE_ISSUE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from invoice.service import InvoiceService
from invoice.schemas.request import (
    InvoiceCreateRequest, InvoiceUpdateRequest, InvoiceTransitionRequest,
    InvoiceLineCreateRequest, InvoiceLineUpdateRequest, PaginateInvoiceRequest,
)
from invoice.schemas.response import (
    InvoiceSummarySchema, InvoiceDetailSchema, InvoiceDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceDetailSchema)
async def create_invoice(
    body: InvoiceCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(INVOICE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """인보이스 생성 — delivery_order_id + prefill_from_do 면 컨테이너 원가로 라인 프리필."""
    return await InvoiceService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[InvoiceSummarySchema])
async def list_invoices(
    request: PaginateInvoiceRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await InvoiceService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[InvoiceSummarySchema])
async def sync_invoices(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await InvoiceService(db, team_id).sync_delta(since)


@router.get("/{invoice_id}", response_model=InvoiceDetailSchema)
async def get_invoice(
    invoice_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await InvoiceService(db, team_id).get(invoice_id)


@router.patch("/{invoice_id}", response_model=InvoiceDetailSchema)
async def update_invoice(
    invoice_id: int,
    body: InvoiceUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(INVOICE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await InvoiceService(db, team_id).update(invoice_id, body, actor_user_id=int(me.id))


@router.delete("/{invoice_id}", response_model=InvoiceDeleteResponseSchema)
async def delete_invoice(
    invoice_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(INVOICE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await InvoiceService(db, team_id).delete(invoice_id, actor_user_id=int(me.id))


@router.post("/{invoice_id}/recompute-cost", response_model=InvoiceDetailSchema)
async def recompute_invoice_cost(
    invoice_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(INVOICE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """연결된 D/O 기준으로 원가(cost_total)만 재계산 (DRAFT)."""
    return await InvoiceService(db, team_id).recompute_cost(invoice_id, actor_user_id=int(me.id))


# ── 라인 ────────────────────────────────────────────────────────
@router.post("/{invoice_id}/lines", response_model=InvoiceDetailSchema)
async def add_invoice_line(
    invoice_id: int,
    body: InvoiceLineCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(INVOICE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await InvoiceService(db, team_id).add_line(invoice_id, body, actor_user_id=int(me.id))


@router.patch("/{invoice_id}/lines/{line_id}", response_model=InvoiceDetailSchema)
async def update_invoice_line(
    invoice_id: int,
    line_id: int,
    body: InvoiceLineUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(INVOICE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await InvoiceService(db, team_id).update_line(invoice_id, line_id, body, actor_user_id=int(me.id))


@router.delete("/{invoice_id}/lines/{line_id}", response_model=InvoiceDetailSchema)
async def delete_invoice_line(
    invoice_id: int,
    line_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(INVOICE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await InvoiceService(db, team_id).delete_line(invoice_id, line_id, actor_user_id=int(me.id))


# ── 상태 전이 (발행/수금/취소) ──────────────────────────────────
@router.post("/{invoice_id}/transition", response_model=InvoiceDetailSchema)
async def transition_invoice(
    invoice_id: int,
    body: InvoiceTransitionRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(INVOICE_ISSUE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """DRAFT→ISSUED→PAID / VOID."""
    return await InvoiceService(db, team_id).transition(invoice_id, body.target, actor_user_id=int(me.id))
