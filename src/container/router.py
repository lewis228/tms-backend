# src/container/router.py
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
from container.service import ContainerService
from container.schemas.request import (
    ContainerCreateRequest, ContainerUpdateRequest,
    PaginateContainerRequest,
    ContainerEventCreateRequest, PaginateContainerEventRequest,
    ContainerBulkDeleteRequest,
)
from container.schemas.response import (
    ContainerResponseSchema, ContainerDeleteResponseSchema,
    ContainerEventResponseSchema, ContainerBulkDeleteResponseSchema,
    ContainerFullResponseSchema,
)


router = APIRouter(prefix="/api/v1/containers", tags=["containers"])


# ─── 단건 CRUD ──────────────────────────────────────────────────

@router.post("", response_model=ContainerResponseSchema)
async def create_container(
    body: ContainerCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ContainerService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[ContainerResponseSchema])
async def list_containers(
    request: PaginateContainerRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ContainerService(db, team_id).list_paginated(request)


@router.get("/{container_id}", response_model=ContainerResponseSchema)
async def get_container(
    container_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ContainerService(db, team_id).get(container_id)


@router.get("/{container_id}/full", response_model=ContainerFullResponseSchema)
async def get_container_full(
    container_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """v3 컨테이너 상세 — D/O 메타 + Stops + Legs(+segments+rate+charges) + Events 한방."""
    return await ContainerService(db, team_id).get_full(container_id)


@router.patch("/{container_id}", response_model=ContainerResponseSchema)
async def update_container(
    container_id: int,
    body: ContainerUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ContainerService(db, team_id).update(container_id, body, actor_user_id=int(me.id))


@router.delete("/{container_id}", response_model=ContainerDeleteResponseSchema)
async def delete_container(
    container_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ContainerService(db, team_id).delete(container_id, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=ContainerBulkDeleteResponseSchema)
async def delete_containers_bulk(
    body: ContainerBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ContainerService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))


# ─── 컨테이너 이벤트 ─────────────────────────────────────────────

@router.post("/{container_id}/events", response_model=ContainerEventResponseSchema)
async def create_container_event(
    container_id: int,
    body: ContainerEventCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await ContainerService(db, team_id).create_event(
        container_id, body, actor_user_id=int(me.id),
    )


@router.get("/{container_id}/events", response_model=list[ContainerEventResponseSchema])
async def list_container_events(
    container_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ContainerService(db, team_id).list_events_by_container(container_id)


@router.get("/events/all", response_model=CursorPaginationResult[ContainerEventResponseSchema])
async def list_all_container_events(
    request: PaginateContainerEventRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await ContainerService(db, team_id).list_events_paginated(request)
