# src/leg_driver_segment/router.py
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

from leg_driver_segment.service import LegDriverSegmentService
from leg_driver_segment.schemas.request import (
    LegDriverSegmentCreateRequest, LegDriverSegmentUpdateRequest,
)
from container.schemas.response import DriverSegmentResponseSchema


router = APIRouter(prefix="/api/v1", tags=["leg-driver-segments"])


@router.get("/legs/{leg_id}/segments", response_model=list[DriverSegmentResponseSchema])
async def list_leg_segments(
    leg_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LegDriverSegmentService(db, team_id).list_by_leg(leg_id)


@router.post("/legs/{leg_id}/segments", response_model=DriverSegmentResponseSchema)
async def create_leg_segment(
    leg_id: int,
    body: LegDriverSegmentCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    body.leg_id = leg_id
    return await LegDriverSegmentService(db, team_id).create(body, actor_user_id=int(me.id))


@router.patch("/leg-segments/{segment_id}", response_model=DriverSegmentResponseSchema)
async def update_leg_segment(
    segment_id: int,
    body: LegDriverSegmentUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegDriverSegmentService(db, team_id).update(segment_id, body, actor_user_id=int(me.id))


@router.delete("/leg-segments/{segment_id}")
async def delete_leg_segment(
    segment_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    ok = await LegDriverSegmentService(db, team_id).delete(segment_id, actor_user_id=int(me.id))
    return {"deleted": ok}
