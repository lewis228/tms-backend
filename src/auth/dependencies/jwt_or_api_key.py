from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from database.dependencies import get_db
from cache.dependencies import get_redis
from api_key.repository import ApiKeyRepository
from team.repository import TeamRepository
from user.repository import UserRepository
from auth.dependencies.bearer_token import bearer_token
from common.exceptions.base import AppException, UnauthorizedException


@dataclass
class AuthResult:
    """Normalized identity extracted from request headers. Either:
      - JWT (from Authorization: Bearer <token>) + optional X-Team-Id
      - API Key (from X-API-Key) → team_id & plan resolved from the key row

    ``team_id`` can be None for JWT callers who haven't selected a team yet
    (e.g. the team-hub page /app). Endpoints that require team scope must
    guard on this themselves.
    """

    auth_type: str  # "jwt" | "api_key"
    user_id: Optional[int]
    team_id: Optional[int]
    plan: str = "free"


async def jwt_or_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthResult:
    # ── 1) API Key path ──────────────────────────────────────────
    # X-API-Key is a B2B machine-to-machine channel (Terminal49-style).
    # The key row carries team_id + plan directly; user_id stays None.
    api_key_raw = request.headers.get("X-API-Key")
    if api_key_raw:
        # 인증 시점엔 아직 team_id 를 모르므로 team_id=None 으로 생성.
        # 이 인스턴스는 get_active_by_key / touch_last_used 만 호출하며, 이 두 메서드는
        # _require_team() 을 부르지 않도록 구현돼 있다.
        auth_repo = ApiKeyRepository(db, team_id=None)
        key_row = await auth_repo.get_active_by_key(api_key_raw)
        if key_row is None:
            raise UnauthorizedException("유효하지 않거나 만료된 API Key입니다.")

        team = await TeamRepository(db).get_team_by_id(key_row.team_id)
        if team is None:
            # Data integrity issue — key points to a deleted team. Treat as
            # invalid rather than leaking "team was deleted" signal.
            raise UnauthorizedException("유효하지 않은 API Key입니다.")

        # Best-effort usage timestamp. If the update fails we don't want to
        # block the request, but since we're already awaiting the session
        # it's cheap enough to do inline.
        await auth_repo.touch_last_used(key_row.id)

        request.state.team = team
        request.state.api_key = key_row
        return AuthResult(
            auth_type="api_key",
            user_id=None,
            team_id=team.id,
            plan=team.plan or "free",
        )

    # ── 2) JWT path ─────────────────────────────────────────────
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth_header[7:])
        await bearer_token(request=request, auth_header=creds, db=db, redis=redis)
        if request.state.token_type != "access":
            raise UnauthorizedException("Access Token이 아닙니다.")
        user_id = int(request.state.payload.get("sub"))

        # X-Team-Id is optional. Endpoints that don't need team scope
        # (e.g. /user/me, team list for team-switcher) can work without it.
        team_id_raw = request.headers.get("X-Team-Id")
        team_id: Optional[int] = None
        plan = "free"

        if team_id_raw:
            try:
                candidate = int(team_id_raw)
            except ValueError:
                raise UnauthorizedException("X-Team-Id 값이 올바르지 않습니다.")

            # Membership check — protects every downstream endpoint.
            # Frontend mirrors this with team:not-member event handling,
            # so returning the distinct code here matters.
            member_team_ids = await UserRepository(db).get_user_team_ids(user_id)
            if candidate not in member_team_ids:
                raise AppException(
                    code="NOT_TEAM_MEMBER",
                    message="해당 팀의 멤버가 아닙니다.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            team = await TeamRepository(db).get_team_by_id(candidate)
            if team is not None:
                team_id = team.id
                plan = team.plan or "free"

        return AuthResult(
            auth_type="jwt",
            user_id=user_id,
            team_id=team_id,
            plan=plan,
        )

    # ── 3) Neither credential present ───────────────────────────
    raise UnauthorizedException(
        "인증이 필요합니다. X-API-Key 또는 Bearer 토큰을 제공하세요.",
    )
