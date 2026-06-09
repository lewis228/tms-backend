# src/rate_multiplier/router.py
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import RATE_SHEET_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from rate_multiplier.service import RateMultiplierService
from rate_multiplier.schemas.request import RateMultiplierUpsertRequest
from rate_multiplier.schemas.response import (
    RateMultiplierResponseSchema, RateMultiplierDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/rate-multipliers", tags=["rate-multipliers"])


@router.get("", response_model=List[RateMultiplierResponseSchema])
async def list_rate_multipliers(
    rate_group_id: Optional[int] = Query(default=None),
    include_inactive: bool = Query(default=False),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """배율 목록 (전역 + 그룹 override)."""
    return await RateMultiplierService(db, team_id).list_all(
        rate_group_id=rate_group_id, include_inactive=include_inactive,
    )


@router.put("", response_model=RateMultiplierResponseSchema)
async def upsert_rate_multiplier(
    body: RateMultiplierUpsertRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_SHEET_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """배율 등록/수정 (scope+size 단위 upsert)."""
    return await RateMultiplierService(db, team_id).upsert(body, actor_user_id=int(me.id))


@router.delete("/{multiplier_id}", response_model=RateMultiplierDeleteResponseSchema)
async def delete_rate_multiplier(
    multiplier_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_SHEET_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """배율 삭제(소프트) — 삭제 시 기본값 폴백."""
    return await RateMultiplierService(db, team_id).delete(multiplier_id, actor_user_id=int(me.id))
