# team/dependencies/get_team_scope.py
"""
X-Team-Id 헤더에서 팀 ID를 추출하고, 요청 유저의 팀 소속 여부를 검증한다.

검증 순서:
  0) 헤더 없으면 → 토큰 claim 의 team_id fallback (DRIVER 1:1 가정) — DB/Redis 0
  1) Redis 캐시 (RBAC 메타 또는 멤버십 캐시) → O(1)
  2) 캐시 미스 시 DB 조회 → user_team 테이블 EXISTS
  3) 비소속 → 403 Forbidden
"""
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from database.dependencies import get_read_db
from cache.dependencies import get_read_redis, get_write_redis
from rbac.cache_service import USER_TEAM_META_KEY, TEAM_SCOPE_KEY
from common.const.settings import settings


_MEMBER_TTL = settings.RBAC_USER_TEAM_TTL


async def get_team_scope(
    request: Request,
    x_team_id: int | None = Header(None, alias="X-Team-Id"),
    r_redis: Redis = Depends(get_read_redis),
    w_redis: Redis = Depends(get_write_redis),
    db: AsyncSession = Depends(get_read_db),
) -> int:
    # ── Fallback: 헤더 없으면 토큰 claim 의 team_id 사용 (DRIVER 1:1 가정) ──
    # DRIVER 는 한 운전기사 = 한 회사 → 토큰 발급 시 access_payload 에 team_id 박힘.
    # bearer_token 가드가 raw JWT payload 를 request.state.payload 에 저장 (decode 결과 dict).
    # request.state.user 는 UserResponseSchema 라 team_id 필드 없음 → payload 를 직접 본다.
    # DB / Redis 추가 호출 0 — O(1) 추출. JWT 서명으로 위변조 차단.
    # Dispatcher / Admin 은 토큰에 team_id claim 없음 (N:M) → 기존 헤더 검증 경로 그대로.
    if x_team_id is None:
        payload = getattr(request.state, "payload", None)
        if isinstance(payload, dict):
            token_team_id = payload.get("team_id")
            if token_team_id is not None:
                return int(token_team_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Team-Id header 가 없다.",
        )

    # AuthMiddleware가 토큰 디코딩 → request.state.user 세팅
    # 토큰이 없거나 무효하면 user 없음 → access_token 가드가 401 처리
    user = getattr(request.state, "user", None)
    if not user:
        return x_team_id

    uid_raw = getattr(user, "id", None)
    if uid_raw is None and isinstance(user, dict):
        uid_raw = user.get("id")
    if uid_raw is None:
        return x_team_id

    uid = int(uid_raw)

    # ── 1) Redis 캐시: RBAC 메타 캐시 또는 멤버십 캐시 확인 ──
    rbac_key = USER_TEAM_META_KEY.format(uid=uid, tid=x_team_id)
    member_key = TEAM_SCOPE_KEY.format(uid=uid, tid=x_team_id)

    pipe = r_redis.pipeline()
    pipe.exists(rbac_key)
    pipe.exists(member_key)
    rbac_hit, member_hit = await pipe.execute()

    if rbac_hit or member_hit:
        return x_team_id

    # ── 2) DB 멤버십 확인 ──
    from team.model import UserTeamModel  # 순환 import 방지

    row = await db.scalar(
        select(UserTeamModel.id).where(
            UserTeamModel.user_id == uid,
            UserTeamModel.team_id == x_team_id,
            UserTeamModel.is_active.is_(True),
        ).limit(1)
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_TEAM_MEMBER",
                "message": "해당 팀에 대한 접근 권한이 없습니다.",
            },
        )

    # ── 3) 멤버십 캐시 저장 ──
    await w_redis.set(member_key, "1", ex=_MEMBER_TTL)

    return x_team_id
