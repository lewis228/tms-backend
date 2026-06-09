# src/dual_transaction/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import LEG_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from dual_transaction.service import DualTransactionService
from dual_transaction.schemas.request import (
    DualTransactionCreateRequest, DualTransactionUpdateRequest, PaginateDualTransactionRequest,
)
from dual_transaction.schemas.response import (
    DualTransactionResponseSchema, DualTransactionDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/dual-transactions", tags=["dual-transactions"])


@router.post("", response_model=DualTransactionResponseSchema)
async def create_dual_transaction(
    body: DualTransactionCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """반납 leg + 픽업 leg 를 한 드라이버로 묶고 두 leg 를 배차."""
    return await DualTransactionService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[DualTransactionResponseSchema])
async def list_dual_transactions(
    request: PaginateDualTransactionRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DualTransactionService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[DualTransactionResponseSchema])
async def sync_dual_transactions(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DualTransactionService(db, team_id).sync_delta(since)


@router.get("/{dtx_id}", response_model=DualTransactionResponseSchema)
async def get_dual_transaction(
    dtx_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DualTransactionService(db, team_id).get(dtx_id)


@router.patch("/{dtx_id}", response_model=DualTransactionResponseSchema)
async def update_dual_transaction(
    dtx_id: int,
    body: DualTransactionUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DualTransactionService(db, team_id).update(dtx_id, body, actor_user_id=int(me.id))


@router.post("/{dtx_id}/complete", response_model=DualTransactionResponseSchema)
async def complete_dual_transaction(
    dtx_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DualTransactionService(db, team_id).complete(dtx_id, actor_user_id=int(me.id))


@router.post("/{dtx_id}/cancel", response_model=DualTransactionResponseSchema)
async def cancel_dual_transaction(
    dtx_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DualTransactionService(db, team_id).cancel(dtx_id, actor_user_id=int(me.id))


@router.delete("/{dtx_id}", response_model=DualTransactionDeleteResponseSchema)
async def delete_dual_transaction(
    dtx_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DualTransactionService(db, team_id).delete(dtx_id, actor_user_id=int(me.id))
