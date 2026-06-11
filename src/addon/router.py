# src/addon/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import ADDON_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from addon.service import AddonService
from addon.schemas.request import (
    AddonCreateRequest, AddonUpdateRequest, PaginateAddonRequest, AddonDriverRateUpsertRequest,
)
from addon.schemas.response import (
    AddonResponseSchema, AddonDeleteResponseSchema, AddonSeedResultSchema,
    AddonDriverRateResponseSchema, AddonDriverRateDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/addons", tags=["addons"])


@router.post("", response_model=AddonResponseSchema)
async def create_addon(
    body: AddonCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(ADDON_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """부가요금 규칙 생성."""
    return await AddonService(db, team_id).create(body, actor_user_id=int(me.id))


@router.post("/seed-defaults", response_model=AddonSeedResultSchema)
async def seed_default_addons(
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(ADDON_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """시스템 기본 부가요금 타입 시드(NGT/PPS/STP/DET/FUEL…)."""
    return await AddonService(db, team_id).seed_defaults(actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[AddonResponseSchema])
async def list_addons(
    request: PaginateAddonRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """부가요금 규칙 목록."""
    return await AddonService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[AddonResponseSchema])
async def sync_addons(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await AddonService(db, team_id).sync_delta(since)


@router.get("/{acc_id}", response_model=AddonResponseSchema)
async def get_addon(
    acc_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await AddonService(db, team_id).get(acc_id)


@router.put("/{acc_id}", response_model=AddonResponseSchema)
async def update_addon(
    acc_id: int,
    body: AddonUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(ADDON_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await AddonService(db, team_id).update(acc_id, body, actor_user_id=int(me.id))


@router.delete("/{acc_id}", response_model=AddonDeleteResponseSchema)
async def delete_addon(
    acc_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(ADDON_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await AddonService(db, team_id).delete(acc_id, actor_user_id=int(me.id))


# ── 기사별 금액 override (addon_driver_rate) ─────────────────────
@router.get("/{addon_id}/driver-rates", response_model=list[AddonDriverRateResponseSchema])
async def list_addon_driver_rates(
    addon_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """이 add-on 의 기사별 금액 override 목록."""
    return await AddonService(db, team_id).list_driver_rates(addon_id)


@router.put("/{addon_id}/driver-rates/{driver_id}", response_model=AddonDriverRateResponseSchema)
async def upsert_addon_driver_rate(
    addon_id: int,
    driver_id: int,
    body: AddonDriverRateUpsertRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(ADDON_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """기사별 금액 override 업서트 — 마스터 정의는 그대로, 금액(amount/percent)만."""
    return await AddonService(db, team_id).upsert_driver_rate(addon_id, driver_id, body, actor_user_id=int(me.id))


@router.delete("/{addon_id}/driver-rates/{driver_id}", response_model=AddonDriverRateDeleteResponseSchema)
async def delete_addon_driver_rate(
    addon_id: int,
    driver_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(ADDON_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """기사별 금액 override 삭제(소프트) → 그 기사는 팀 기본값으로 복귀."""
    return await AddonService(db, team_id).delete_driver_rate(addon_id, driver_id, actor_user_id=int(me.id))
