# src/leg_charge/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import LEG_CHARGE_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from leg_charge.service import LegChargeService
from leg_charge.schemas.request import (
    LegChargeCreateRequest, LegChargeUpdateRequest,
    PaginateLegChargeRequest, LegChargeBulkDeleteRequest,
)
from leg_charge.schemas.response import (
    LegChargeResponseSchema, LegChargeDeleteResponseSchema,
    LegChargeBulkDeleteResponseSchema,
)


router = APIRouter(prefix="/api/v1/leg-charges", tags=["leg-charges"])


@router.post("", response_model=LegChargeResponseSchema)
async def create_leg_charge(
    body: LegChargeCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_CHARGE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegChargeService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[LegChargeResponseSchema])
async def list_leg_charges(
    request: PaginateLegChargeRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LegChargeService(db, team_id).list_paginated(request)


@router.get("/by-leg/{leg_id}", response_model=list[LegChargeResponseSchema])
async def list_leg_charges_by_leg(
    leg_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LegChargeService(db, team_id).list_by_leg(leg_id)


@router.post("/auto-match/{leg_id}", response_model=list[LegChargeResponseSchema])
async def auto_match_leg_charges(
    leg_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_CHARGE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """leg 1건의 자동 charge 매칭 (rate_card + chassis_event + leg_stop WAIT).
    이미 AUTO source 가 있으면 skip (idempotent)."""
    return await LegChargeService(db, team_id).auto_match(leg_id, actor_user_id=int(me.id))


@router.get("/{id_}", response_model=LegChargeResponseSchema)
async def get_leg_charge(
    id_: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LegChargeService(db, team_id).get(id_)


@router.patch("/{id_}", response_model=LegChargeResponseSchema)
async def update_leg_charge(
    id_: int,
    body: LegChargeUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_CHARGE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegChargeService(db, team_id).update(id_, body, actor_user_id=int(me.id))


@router.delete("/{id_}", response_model=LegChargeDeleteResponseSchema)
async def delete_leg_charge(
    id_: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_CHARGE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegChargeService(db, team_id).delete(id_, actor_user_id=int(me.id))


@router.post("/bulk/delete", response_model=LegChargeBulkDeleteResponseSchema)
async def delete_leg_charges_bulk(
    body: LegChargeBulkDeleteRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LEG_CHARGE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await LegChargeService(db, team_id).delete_bulk(body, actor_user_id=int(me.id))
