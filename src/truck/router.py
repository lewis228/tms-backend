# src/truck/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import TRUCK_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from truck.service import TruckService
from truck.schemas.request import (
    TruckCreateRequest, TruckUpdateRequest,
    PaginateTruckRequest, TruckBulkDeleteRequest,
)
from truck.schemas.response import (
    TruckResponseSchema, TruckDeleteResponseSchema,
    TruckBulkDeleteResponseSchema,
)


router = APIRouter(prefix="/api/v1/trucks", tags=["trucks"])


@router.post("", response_model=TruckResponseSchema)
async def create_truck(
    body: TruckCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TRUCK_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await TruckService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[TruckResponseSchema])
async def list_trucks(
    request: PaginateTruckRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await TruckService(db, team_id).list_paginated(request)


@router.get("/{id_}", response_model=TruckResponseSchema)
async def get_truck(
    id_: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await TruckService(db, team_id).get(id_)


@router.patch("/{id_}", response_model=TruckResponseSchema)
async def update_truck(
    id_: int,
    body: TruckUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TRUCK_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await TruckService(db, team_id).update(id_, body, actor_user_id=int(me.id))


@router.delete("/{id_}", response_model=TruckDeleteResponseSchema)
async def delete_truck(
    id_: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TRUCK_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await TruckService(db, team_id).delete(id_, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=TruckBulkDeleteResponseSchema)
async def delete_trucks_bulk(
    body: TruckBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TRUCK_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await TruckService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))
