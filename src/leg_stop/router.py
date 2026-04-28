# src/leg_stop/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import LEG_STOP_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from leg_stop.service import LegStopService
from leg_stop.schemas.request import (
    LegStopCreateRequest, LegStopUpdateRequest,
    PaginateLegStopRequest, LegStopBulkDeleteRequest,
)
from leg_stop.schemas.response import (
    LegStopResponseSchema, LegStopDeleteResponseSchema,
    LegStopBulkDeleteResponseSchema,
)


router = APIRouter(prefix="/api/v1/leg-stops", tags=["leg-stops"])


@router.post("", response_model=LegStopResponseSchema)
async def create_leg_stop(
    body: LegStopCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_STOP_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegStopService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[LegStopResponseSchema])
async def list_leg_stops(
    request: PaginateLegStopRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LegStopService(db, team_id).list_paginated(request)


@router.get("/by-leg/{leg_id}", response_model=list[LegStopResponseSchema])
async def list_leg_stops_by_leg(
    leg_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LegStopService(db, team_id).list_by_leg(leg_id)


@router.get("/{id_}", response_model=LegStopResponseSchema)
async def get_leg_stop(
    id_: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LegStopService(db, team_id).get(id_)


@router.patch("/{id_}", response_model=LegStopResponseSchema)
async def update_leg_stop(
    id_: int,
    body: LegStopUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_STOP_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegStopService(db, team_id).update(id_, body, actor_user_id=int(me.id))


@router.delete("/{id_}", response_model=LegStopDeleteResponseSchema)
async def delete_leg_stop(
    id_: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_STOP_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegStopService(db, team_id).delete(id_, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=LegStopBulkDeleteResponseSchema)
async def delete_leg_stops_bulk(
    body: LegStopBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_STOP_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegStopService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))
