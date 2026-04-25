from __future__ import annotations
from typing import Set, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from database.dependencies import get_db
from cache.dependencies import get_redis
from rbac.repository import RbacRepository
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema


def _extract_team_id(request: Request) -> Optional[int]:
    raw = (
        request.path_params.get("team_id")
        or request.query_params.get("teamId")
        or request.headers.get("X-Team-Id")
    )
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def permission_guard(*required_codes: str):
    required: Set[str] = set(required_codes)

    async def guard(
        request: Request,
        me: UserResponseSchema = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        redis: Redis = Depends(get_redis),
    ):
        team_id = _extract_team_id(request)
        repo = RbacRepository(db, redis)
        codes, group_id, version, is_admin_group = await repo.get_user_perm_meta(int(me.id), team_id=team_id)

        if is_admin_group:
            return

        if team_id is None or codes is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "TEAM_REQUIRED", "message": "Team context is required."})

        if required and required.isdisjoint(codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "PERMISSION_DENIED", "message": "You do not have permission for this action.", "missing": list(required), "groupId": group_id, "groupVersion": version},
            )

    return guard


async def team_admin_guard(
    request: Request,
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    team_id = _extract_team_id(request)
    repo = RbacRepository(db, redis)
    codes, group_id, version, is_admin = await repo.get_user_perm_meta(int(me.id), team_id=team_id)
    if is_admin:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "PERMISSION_DENIED", "message": "Admin-only action.", "groupId": group_id, "groupVersion": version},
    )
