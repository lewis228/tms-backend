# src/rate_tariff/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import DO_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema
from common.pagination.schemas.pagination_response import CursorPaginationResult

from rate_tariff.service import RateTariffService
from rate_tariff.schemas.request import (
    RateTariffCreateRequest, RateTariffUpdateRequest, PaginateRateTariffRequest,
)
from rate_tariff.schemas.response import RateTariffResponseSchema


router = APIRouter(prefix="/api/v1/rate-tariffs", tags=["rate-tariffs"])


@router.get("", response_model=CursorPaginationResult[RateTariffResponseSchema])
async def list_rate_tariffs(
    request: PaginateRateTariffRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await RateTariffService(db, team_id).list_paginated(request)


@router.post("", response_model=RateTariffResponseSchema)
async def create_rate_tariff(
    body: RateTariffCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await RateTariffService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("/{tariff_id}", response_model=RateTariffResponseSchema)
async def get_rate_tariff(
    tariff_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await RateTariffService(db, team_id).get(tariff_id)


@router.patch("/{tariff_id}", response_model=RateTariffResponseSchema)
async def update_rate_tariff(
    tariff_id: int,
    body: RateTariffUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await RateTariffService(db, team_id).update(tariff_id, body, actor_user_id=int(me.id))


@router.delete("/{tariff_id}")
async def delete_rate_tariff(
    tariff_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    ok = await RateTariffService(db, team_id).delete(tariff_id, actor_user_id=int(me.id))
    return {"deleted": ok}
