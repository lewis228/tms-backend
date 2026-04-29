# src/rate_quote/router.py
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

from rate_quote.service import RateQuoteService
from rate_quote.schemas.request import (
    RateQuoteCreateRequest, RateQuoteUpdateRequest, PaginateRateQuoteRequest,
)
from rate_quote.schemas.response import RateQuoteResponseSchema


router = APIRouter(prefix="/api/v1/rate-quotes", tags=["rate-quotes"])


@router.get("", response_model=CursorPaginationResult[RateQuoteResponseSchema])
async def list_rate_quotes(
    request: PaginateRateQuoteRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await RateQuoteService(db, team_id).list_paginated(request)


@router.post("", response_model=RateQuoteResponseSchema)
async def create_rate_quote(
    body: RateQuoteCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await RateQuoteService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("/{quote_id}", response_model=RateQuoteResponseSchema)
async def get_rate_quote(
    quote_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await RateQuoteService(db, team_id).get(quote_id)


@router.patch("/{quote_id}", response_model=RateQuoteResponseSchema)
async def update_rate_quote(
    quote_id: int,
    body: RateQuoteUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await RateQuoteService(db, team_id).update(quote_id, body, actor_user_id=int(me.id))


@router.delete("/{quote_id}")
async def delete_rate_quote(
    quote_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    ok = await RateQuoteService(db, team_id).delete(quote_id, actor_user_id=int(me.id))
    return {"deleted": ok}
