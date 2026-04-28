# src/charge_code/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import CHARGE_CODE_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from charge_code.service import ChargeCodeService
from charge_code.schemas.request import (
    ChargeCodeCreateRequest, ChargeCodeUpdateRequest,
    PaginateChargeCodeRequest, ChargeCodeBulkDeleteRequest,
)
from charge_code.schemas.response import (
    ChargeCodeResponseSchema, ChargeCodeDeleteResponseSchema,
    ChargeCodeBulkDeleteResponseSchema,
)


router = APIRouter(prefix="/api/v1/charge-codes", tags=["charge-codes"])


@router.post("", response_model=ChargeCodeResponseSchema)
async def create_charge_code(
    body: ChargeCodeCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHARGE_CODE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChargeCodeService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[ChargeCodeResponseSchema])
async def list_charge_codes(
    request: PaginateChargeCodeRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ChargeCodeService(db, team_id).list_paginated(request)


@router.get("/{id_}", response_model=ChargeCodeResponseSchema)
async def get_charge_code(
    id_: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ChargeCodeService(db, team_id).get(id_)


@router.patch("/{id_}", response_model=ChargeCodeResponseSchema)
async def update_charge_code(
    id_: int,
    body: ChargeCodeUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHARGE_CODE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChargeCodeService(db, team_id).update(id_, body, actor_user_id=int(me.id))


@router.delete("/{id_}", response_model=ChargeCodeDeleteResponseSchema)
async def delete_charge_code(
    id_: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHARGE_CODE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChargeCodeService(db, team_id).delete(id_, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=ChargeCodeBulkDeleteResponseSchema)
async def delete_charge_codes_bulk(
    body: ChargeCodeBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHARGE_CODE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChargeCodeService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))
