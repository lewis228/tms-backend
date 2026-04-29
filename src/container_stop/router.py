# src/container_stop/router.py
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

from container_stop.service import ContainerStopService
from container_stop.schemas.request import (
    ContainerStopCreateRequest, ContainerStopUpdateRequest,
    ContainerStopReorderRequest,
)
from container.schemas.response import StopResponseSchema


router = APIRouter(prefix="/api/v1", tags=["container-stops"])


@router.get("/containers/{container_id}/stops", response_model=list[StopResponseSchema])
async def list_container_stops(
    container_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ContainerStopService(db, team_id).list_by_container(container_id)


@router.post("/containers/{container_id}/stops", response_model=StopResponseSchema)
async def create_container_stop(
    container_id: int,
    body: ContainerStopCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    # path container_id 강제
    body.container_id = container_id
    return await ContainerStopService(db, team_id).create(body, actor_user_id=int(me.id))


@router.patch("/container-stops/{stop_id}", response_model=StopResponseSchema)
async def update_container_stop(
    stop_id: int,
    body: ContainerStopUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ContainerStopService(db, team_id).update(stop_id, body, actor_user_id=int(me.id))


@router.post("/containers/{container_id}/stops/reorder", response_model=list[StopResponseSchema])
async def reorder_container_stops(
    container_id: int,
    body: ContainerStopReorderRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ContainerStopService(db, team_id).reorder(
        container_id,
        [{"stop_id": it.stop_id, "sequence_no": it.sequence_no} for it in body.items],
        actor_user_id=int(me.id),
    )


@router.delete("/container-stops/{stop_id}")
async def delete_container_stop(
    stop_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    ok = await ContainerStopService(db, team_id).delete(stop_id, actor_user_id=int(me.id))
    return {"deleted": ok}
