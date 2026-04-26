# tenant/dependencies/get_tenant_scope.py
"""
X-Tenant-Id 헤더에서 팀 ID를 추출하고, 요청 유저의 팀 소속 여부를 검증한다.

검증 순서:
  1) Redis 캐시 (RBAC 메타 또는 멤버십 캐시) → O(1)
  2) 캐시 미스 시 DB 조회 → user_tenants 테이블 EXISTS
  3) 비소속 → 403 Forbidden
"""
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from database.dependencies import get_read_db
from cache.dependencies import get_read_redis, get_write_redis
from rbac.cache_service import USER_TENANT_META_KEY, TENANT_SCOPE_KEY
from common.const.settings import settings


_MEMBER_TTL = settings.RBAC_USER_TENANT_TTL


async def get_tenant_scope(
    request: Request,
    x_tenant_id: int | None = Header(None, alias="X-Tenant-Id"),
    r_redis: Redis = Depends(get_read_redis),
    w_redis: Redis = Depends(get_write_redis),
    db: AsyncSession = Depends(get_read_db),
) -> int:
    if x_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-Id header 가 없다.",
        )

    # AuthMiddleware가 토큰 디코딩 → request.state.user 세팅
    # 토큰이 없거나 무효하면 user 없음 → access_token 가드가 401 처리
    user = getattr(request.state, "user", None)
    if not user:
        return x_tenant_id

    uid_raw = getattr(user, "id", None)
    if uid_raw is None and isinstance(user, dict):
        uid_raw = user.get("id")
    if uid_raw is None:
        return x_tenant_id

    uid = int(uid_raw)

    # ── 1) Redis 캐시: RBAC 메타 캐시 또는 멤버십 캐시 확인 ──
    rbac_key = USER_TENANT_META_KEY.format(uid=uid, tid=x_tenant_id)
    member_key = TENANT_SCOPE_KEY.format(uid=uid, tid=x_tenant_id)

    pipe = r_redis.pipeline()
    pipe.exists(rbac_key)
    pipe.exists(member_key)
    rbac_hit, member_hit = await pipe.execute()

    if rbac_hit or member_hit:
        return x_tenant_id

    # ── 2) DB 멤버십 확인 ──
    from tenant.model import UserTenantModel  # 순환 import 방지

    row = await db.scalar(
        select(UserTenantModel.id).where(
            UserTenantModel.user_id == uid,
            UserTenantModel.tenant_id == x_tenant_id,
            UserTenantModel.is_active.is_(True),
        ).limit(1)
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_TENANT_MEMBER",
                "message": "해당 팀에 대한 접근 권한이 없습니다.",
            },
        )

    # ── 3) 멤버십 캐시 저장 ──
    await w_redis.set(member_key, "1", ex=_MEMBER_TTL)

    return x_tenant_id
