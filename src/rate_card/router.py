# src/rate_card/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import RATE_CARD_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from rate_card.service import RateCardService
from rate_card.schemas.request import (
    RateCardCreateRequest, RateCardUpdateRequest,
    PaginateRateCardRequest, RateCardBulkDeleteRequest,
)
from rate_card.schemas.response import (
    RateCardResponseSchema, RateCardDeleteResponseSchema,
    RateCardBulkDeleteResponseSchema,
)


router = APIRouter(prefix="/api/v1/rate-cards", tags=["rate-cards"])


@router.post("", response_model=RateCardResponseSchema)
async def create_rate_card(
    body: RateCardCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_CARD_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await RateCardService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[RateCardResponseSchema])
async def list_rate_cards(
    request: PaginateRateCardRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await RateCardService(db, team_id).list_paginated(request)


@router.get("/{id_}", response_model=RateCardResponseSchema)
async def get_rate_card(
    id_: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await RateCardService(db, team_id).get(id_)


@router.patch("/{id_}", response_model=RateCardResponseSchema)
async def update_rate_card(
    id_: int,
    body: RateCardUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_CARD_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await RateCardService(db, team_id).update(id_, body, actor_user_id=int(me.id))


@router.delete("/{id_}", response_model=RateCardDeleteResponseSchema)
async def delete_rate_card(
    id_: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_CARD_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await RateCardService(db, team_id).delete(id_, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=RateCardBulkDeleteResponseSchema)
async def delete_rate_cards_bulk(
    body: RateCardBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_CARD_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await RateCardService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))
