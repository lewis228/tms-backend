# src/payroll/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import (
    SETTLEMENT_CALCULATE, SETTLEMENT_ADJUST, SETTLEMENT_APPROVE, SETTLEMENT_UNAPPROVE, SETTLEMENT_WRITE,
)
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from payroll.service import PayrollService
from payroll.schemas.request import (
    PayrollBuildRequest, PayrollBuildPeriodRequest, PayrollChargeAddRequest, PaginatePayrollRequest,
)
from payroll.schemas.response import (
    PayrollSummarySchema, PayrollDetailSchema, PayrollPreviewSchema, PayrollDeleteResponseSchema,
    PayrollPeriodSummarySchema, PayrollBuildPeriodResultSchema,
)
from payroll.periods import biweekly_period

router = APIRouter(prefix="/api/v1/payroll", tags=["payroll"])


@router.post("/preview", response_model=PayrollPreviewSchema)
async def preview_payroll(
    body: PayrollBuildRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_CALCULATE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """드라이버×기간 정산 미리보기(저장 안 함) — RateResolver 로 leg base 산출."""
    return await PayrollService(db, team_id).preview(body)


@router.post("", response_model=PayrollDetailSchema)
async def build_payroll(
    body: PayrollBuildRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_CALCULATE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """드라이버×기간 정산 생성(DRAFT) — leg 요율 snapshot 라인."""
    return await PayrollService(db, team_id).build(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[PayrollSummarySchema])
async def list_payroll(
    request: PaginatePayrollRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await PayrollService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[PayrollSummarySchema])
async def sync_payroll(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await PayrollService(db, team_id).sync_delta(since)


@router.get("/biweekly-period", response_model=PayrollPeriodSummarySchema)
async def get_biweekly_period(
    ref: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """ref 일자가 속한 격주 기간 + 해당 기간 정산 집계."""
    from datetime import date as _date
    start, end = biweekly_period(_date.fromisoformat(ref))
    return await PayrollService(db, team_id).period_summary(start, end)


@router.get("/period-summary", response_model=PayrollPeriodSummarySchema)
async def get_period_summary(
    period_start: str,
    period_end: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """임의 기간 정산 집계(드라이버 수/건수/합계)."""
    from datetime import date as _date
    return await PayrollService(db, team_id).period_summary(
        _date.fromisoformat(period_start), _date.fromisoformat(period_end),
    )


@router.post("/build-period", response_model=PayrollBuildPeriodResultSchema)
async def build_period_payroll(
    body: PayrollBuildPeriodRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_CALCULATE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """격주 등 기간에 대해 대상 드라이버 전체 정산 일괄 생성(DRAFT)."""
    return await PayrollService(db, team_id).build_period(body, actor_user_id=int(me.id))


@router.get("/{settlement_id}", response_model=PayrollDetailSchema)
async def get_payroll(
    settlement_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await PayrollService(db, team_id).get(settlement_id)


@router.post("/{settlement_id}/confirm", response_model=PayrollDetailSchema)
async def confirm_payroll(
    settlement_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_APPROVE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """정산 확정 — 미등록 요율 라인 있으면 차단."""
    return await PayrollService(db, team_id).confirm(settlement_id, actor_user_id=int(me.id))


@router.post("/{settlement_id}/paid", response_model=PayrollDetailSchema)
async def pay_payroll(
    settlement_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_APPROVE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await PayrollService(db, team_id).mark_paid(settlement_id, actor_user_id=int(me.id))


@router.post("/{settlement_id}/void", response_model=PayrollDetailSchema)
async def void_payroll(
    settlement_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_UNAPPROVE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await PayrollService(db, team_id).void(settlement_id, actor_user_id=int(me.id))


@router.post("/{settlement_id}/charges", response_model=PayrollDetailSchema)
async def add_payroll_charge(
    settlement_id: int,
    body: PayrollChargeAddRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_ADJUST)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """정산에 addon(부가요금) 추가."""
    return await PayrollService(db, team_id).add_charge(settlement_id, body, actor_user_id=int(me.id))


@router.delete("/{settlement_id}", response_model=PayrollDeleteResponseSchema)
async def delete_payroll(
    settlement_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(SETTLEMENT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await PayrollService(db, team_id).delete(settlement_id, actor_user_id=int(me.id))
