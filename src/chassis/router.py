# src/chassis/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import CHASSIS_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from chassis.service import ChassisService
from chassis.schemas.request import (
    ChassisCreateRequest, ChassisUpdateRequest,
    PaginateChassisRequest, ChassisBulkDeleteRequest,
)
from chassis.schemas.response import (
    ChassisResponseSchema, ChassisDeleteResponseSchema,
    ChassisBulkDeleteResponseSchema,
)


router = APIRouter(prefix="/api/v1/chassis", tags=["chassis"])


@router.post("", response_model=ChassisResponseSchema)
async def create_chassis(
    body: ChassisCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHASSIS_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChassisService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[ChassisResponseSchema])
async def list_chassis(
    request: PaginateChassisRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ChassisService(db, team_id).list_paginated(request)


@router.get("/{id_}", response_model=ChassisResponseSchema)
async def get_chassis(
    id_: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ChassisService(db, team_id).get(id_)


@router.patch("/{id_}", response_model=ChassisResponseSchema)
async def update_chassis(
    id_: int,
    body: ChassisUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHASSIS_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChassisService(db, team_id).update(id_, body, actor_user_id=int(me.id))


@router.delete("/{id_}", response_model=ChassisDeleteResponseSchema)
async def delete_chassis(
    id_: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHASSIS_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChassisService(db, team_id).delete(id_, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=ChassisBulkDeleteResponseSchema)
async def delete_chassis_bulk(
    body: ChassisBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHASSIS_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChassisService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))
