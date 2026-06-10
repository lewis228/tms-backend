# src/delivery_order/addon_router.py
"""D/O 단위 Add-on CRUD (고객 청구용)."""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import DO_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from delivery_order.addon_service import DoAddonService
from delivery_order.addon_schemas import (
    DoAddonCreateRequest, DoAddonUpdateRequest, DoAddonResponseSchema, DoAddonDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/delivery-orders", tags=["delivery-order-addons"])


@router.get("/{do_id}/addons", response_model=List[DoAddonResponseSchema])
async def list_do_addons(
    do_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DoAddonService(db, team_id).list_addons(do_id)


@router.post("/{do_id}/addons", response_model=DoAddonResponseSchema)
async def add_do_addon(
    do_id: int,
    body: DoAddonCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    body.delivery_order_id = do_id
    return await DoAddonService(db, team_id).add_addon(body, actor_user_id=int(me.id))


@router.patch("/addons/{addon_id}", response_model=DoAddonResponseSchema)
async def update_do_addon(
    addon_id: int,
    body: DoAddonUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DoAddonService(db, team_id).update_addon(addon_id, body, actor_user_id=int(me.id))


@router.delete("/addons/{addon_id}", response_model=DoAddonDeleteResponseSchema)
async def delete_do_addon(
    addon_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    return await DoAddonService(db, team_id).delete_addon(addon_id)
