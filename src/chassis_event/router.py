# src/chassis_event/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import CHASSIS_EVENT_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from chassis_event.service import ChassisEventService
from chassis_event.schemas.request import (
    ChassisEventCreateRequest, PaginateChassisEventRequest,
)
from chassis_event.schemas.response import ChassisEventResponseSchema


router = APIRouter(prefix="/api/v1/chassis-events", tags=["chassis-events"])


@router.post("", response_model=ChassisEventResponseSchema)
async def create_chassis_event(
    body: ChassisEventCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(CHASSIS_EVENT_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ChassisEventService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[ChassisEventResponseSchema])
async def list_chassis_events(
    request: PaginateChassisEventRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ChassisEventService(db, team_id).list_paginated(request)


@router.get("/by-chassis/{chassis_id}", response_model=list[ChassisEventResponseSchema])
async def list_chassis_events_by_chassis(
    chassis_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ChassisEventService(db, team_id).list_by_chassis(chassis_id)
