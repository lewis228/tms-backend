from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database.dependencies import get_write_db, get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema
from team.schemas.request import (
    CreateTeamRequestSchema,
    InviteMemberRequestSchema,
    UpdateTeamRequestSchema,
)
from team.schemas.response import (
    TeamResponseSchema,
    TeamMemberResponseSchema,
    TeamUsageResponseSchema,
)
from team.service import TeamService
from common.exceptions.base import ForbiddenException

router = APIRouter(prefix="/api/v1/team", tags=["team"])


@router.post("", response_model=TeamResponseSchema, status_code=201)
async def create_team(
    body: CreateTeamRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = TeamService(db)
    return await svc.create_team(
        name=body.name,
        email=body.email,
        plan=body.plan or "free",
        creator_user_id=me.id,
    )


@router.get("/{team_id}", response_model=TeamResponseSchema)
async def get_team(
    team_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_read_db),
):
    svc = TeamService(db)
    return await svc.get_team(team_id)


@router.patch("/{team_id}", response_model=TeamResponseSchema)
async def update_team(
    team_id: int,
    body: UpdateTeamRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    _require_team_scope(auth, team_id)
    svc = TeamService(db)
    # exclude_unset keeps the PATCH true to semantics: fields the client
    # didn't touch stay at their current values.
    fields = body.model_dump(exclude_unset=True)
    return await svc.update_team(
        team_id,
        fields=fields,
        updated_by_user_id=int(me.id),
    )


# ── Team members ─────────────────────────────────────────────────


@router.get("/{team_id}/members", response_model=List[TeamMemberResponseSchema])
async def list_team_members(
    team_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_read_db),
):
    _require_team_scope(auth, team_id)
    svc = TeamService(db)
    return await svc.list_members(team_id)


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberResponseSchema,
    status_code=201,
)
async def invite_team_member(
    team_id: int,
    body: InviteMemberRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_write_db),
):
    _require_team_scope(auth, team_id)
    svc = TeamService(db)
    return await svc.invite_member(
        team_id=team_id,
        email=body.email,
        permission_group_id=body.permission_group_id,
    )


@router.delete("/{team_id}/members/{user_id}", status_code=204)
async def remove_team_member(
    team_id: int,
    user_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_write_db),
):
    _require_team_scope(auth, team_id)
    svc = TeamService(db)
    await svc.remove_member(team_id=team_id, user_id=user_id)


# ── Usage analytics ─────────────────────────────────────────────


@router.get("/{team_id}/usage", response_model=TeamUsageResponseSchema)
async def get_team_usage(
    team_id: int,
    days: int = 30,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_read_db),
):
    _require_team_scope(auth, team_id)
    # Cap the window so an over-eager caller can't hammer Redis — 90 days
    # is plenty for dashboard views.
    days = max(1, min(days, 90))
    svc = TeamService(db)
    return await svc.get_usage(team_id, days=days)


def _require_team_scope(auth: AuthResult, team_id: int) -> None:
    """JWT callers may only touch teams they've been scoped to via
    X-Team-Id. API-key callers are inherently bound to a single team via
    their key row, so their scope is honoured implicitly."""
    if auth.auth_type == "jwt" and auth.team_id != team_id:
        raise ForbiddenException("해당 팀에 접근할 권한이 없습니다.")
