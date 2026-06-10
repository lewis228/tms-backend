# src/leg_layer/router.py
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import LEG_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from leg_layer.service import LegLayerService
from leg_layer.schemas.request import (
    LegAddonCreateRequest, LegAddonUpdateRequest,
)
from leg_layer.schemas.response import (
    LegAddonResponseSchema, LegLayerDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1", tags=["leg-layers"])


# ── Leg Add-on (추가요금 한 줄, 중복 가능) ───────────────────
@router.get("/leg-addons", response_model=List[LegAddonResponseSchema])
async def list_leg_addons(
    leg_id: int = Query(...),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LegLayerService(db, team_id).list_addons(leg_id)


@router.post("/leg-addons", response_model=LegAddonResponseSchema)
async def add_leg_addon(
    body: LegAddonCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegLayerService(db, team_id).add_addon(body, actor_user_id=int(me.id))


@router.patch("/leg-addons/{addon_id}", response_model=LegAddonResponseSchema)
async def update_leg_addon(
    addon_id: int,
    body: LegAddonUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegLayerService(db, team_id).update_addon(addon_id, body, actor_user_id=int(me.id))


@router.delete("/leg-addons/{addon_id}", response_model=LegLayerDeleteResponseSchema)
async def delete_leg_addon(
    addon_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    return await LegLayerService(db, team_id).delete_addon(addon_id)
