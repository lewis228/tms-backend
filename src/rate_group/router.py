# src/rate_group/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import RATE_GROUP_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from rate_group.service import RateGroupService
from rate_group.schemas.request import (
    RateGroupCreateRequest, RateGroupUpdateRequest, PaginateRateGroupRequest,
)
from rate_group.schemas.response import (
    RateGroupResponseSchema, RateGroupDeleteResponseSchema,
)

router = APIRouter(prefix="/api/v1/rate-groups", tags=["rate-groups"])


@router.post("", response_model=RateGroupResponseSchema)
async def create_rate_group(
    body: RateGroupCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_GROUP_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Group(정산/요율 그룹) 생성 — 쓰기 권한 필요."""
    return await RateGroupService(db, team_id).create(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[RateGroupResponseSchema])
async def list_rate_groups(
    request: PaginateRateGroupRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Group 목록(커서 페이징)."""
    return await RateGroupService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[RateGroupResponseSchema])
async def sync_rate_groups(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Group Delta Sync."""
    return await RateGroupService(db, team_id).sync_delta(since)


@router.get("/{group_id}", response_model=RateGroupResponseSchema)
async def get_rate_group(
    group_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Group 단건 조회(활성만)."""
    return await RateGroupService(db, team_id).get(group_id)


@router.put("/{group_id}", response_model=RateGroupResponseSchema)
async def update_rate_group(
    group_id: int,
    body: RateGroupUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_GROUP_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Group 수정 — 쓰기 권한 필요."""
    return await RateGroupService(db, team_id).update(group_id, body, actor_user_id=int(me.id))


@router.delete("/{group_id}", response_model=RateGroupDeleteResponseSchema)
async def delete_rate_group(
    group_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_GROUP_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Group 삭제(소프트)."""
    return await RateGroupService(db, team_id).delete(group_id, actor_user_id=int(me.id))
