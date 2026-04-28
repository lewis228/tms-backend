# src/equipment_pool/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import EQUIPMENT_POOL_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from equipment_pool.service import EquipmentPoolService
from equipment_pool.schemas.request import (
    EquipmentPoolCreateRequest, EquipmentPoolUpdateRequest,
    PaginateEquipmentPoolRequest, EquipmentPoolBulkDeleteRequest,
)
from equipment_pool.schemas.response import (
    EquipmentPoolResponseSchema, EquipmentPoolDeleteResponseSchema,
    EquipmentPoolBulkDeleteResponseSchema,
)


router = APIRouter(prefix="/api/v1/equipment-pools", tags=["equipment-pools"])


@router.post("", response_model=EquipmentPoolResponseSchema)
async def create_pool(
    body: EquipmentPoolCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(EQUIPMENT_POOL_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await EquipmentPoolService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[EquipmentPoolResponseSchema])
async def list_pools(
    request: PaginateEquipmentPoolRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await EquipmentPoolService(db, team_id).list_paginated(request)


@router.get("/{id_}", response_model=EquipmentPoolResponseSchema)
async def get_pool(
    id_: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await EquipmentPoolService(db, team_id).get(id_)


@router.patch("/{id_}", response_model=EquipmentPoolResponseSchema)
async def update_pool(
    id_: int,
    body: EquipmentPoolUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(EQUIPMENT_POOL_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await EquipmentPoolService(db, team_id).update(id_, body, actor_user_id=int(me.id))


@router.delete("/{id_}", response_model=EquipmentPoolDeleteResponseSchema)
async def delete_pool(
    id_: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(EQUIPMENT_POOL_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await EquipmentPoolService(db, team_id).delete(id_, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=EquipmentPoolBulkDeleteResponseSchema)
async def delete_pools_bulk(
    body: EquipmentPoolBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(EQUIPMENT_POOL_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await EquipmentPoolService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))
