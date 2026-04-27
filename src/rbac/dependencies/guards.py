# rbac/dependencies/guards.py
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
    """
    우선순위: path param -> query -> header
    /team/{team_id}, ?teamId=123, X-Team-Id
    """
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
    """
    - 플랫폼 운영자(SUPER_ADMIN) 면 무조건 통과
    - team 의 admin_group(is_admin_group=True) 이면 통과
    - team 컨텍스트 없음/미소속 → 403(TEAM_REQUIRED)
    - 필요한 코드 하나도 없으면 → 403(PERMISSION_DENIED) + groupId, groupVersion 제공
    """
    required: Set[str] = set(required_codes)

    async def guard(
        request: Request,
        me: UserResponseSchema = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        redis: Redis = Depends(get_redis),
    ):
        # 플랫폼 운영자는 모든 권한 통과 (team 없이도)
        from user.const.roles import RolesEnum
        if getattr(getattr(me, "role", None), "value", getattr(me, "role", "")) == RolesEnum.SUPER_ADMIN.value:
            return

        team_id = _extract_team_id(request)

        repo = RbacRepository(db, redis)
        codes, group_id, version, is_admin_group = await repo.get_user_perm_meta(
            int(me.id),
            team_id=team_id,
        )

        # team 어드민 그룹이면 통과
        if is_admin_group:
            return

        # team 컨텍스트 없거나 멤버가 아닌 경우
        if team_id is None or codes is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "TEAM_REQUIRED",
                    "message": "team 컨텍스트가 필요합니다.",
                },
            )

        # 필요한 권한 코드가 하나도 없으면 거부
        if required and required.isdisjoint(codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PERMISSION_DENIED",
                    "message": "해당 기능에 대한 권한이 없습니다.\n권한 요청은 관리자에게 문의해 주세요.",
                    "missing": list(required),
                    "groupId": group_id,
                    "groupVersion": version,
                },
            )

    return guard


# ═══════════════════════════════════════════════════════════════
# team 관리자 전용 가드 (admin_group 만 허용)
# ═══════════════════════════════════════════════════════════════

async def team_admin_guard(
    request: Request,
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """
    team 내 admin_group 또는 SUPER_ADMIN 만 허용.
    """
    from user.const.roles import RolesEnum
    if getattr(getattr(me, "role", None), "value", getattr(me, "role", "")) == RolesEnum.SUPER_ADMIN.value:
        return

    team_id = _extract_team_id(request)
    repo = RbacRepository(db, redis)
    codes, group_id, version, is_admin = await repo.get_user_perm_meta(
        int(me.id), team_id=team_id,
    )
    if is_admin:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "PERMISSION_DENIED",
            "message": "관리자만 가능한 기능입니다.\n권한 요청은 관리자에게 문의해 주세요.",
            "groupId": group_id,
            "groupVersion": version,
        },
    )
