from __future__ import annotations
import json
from typing import Optional, Set, Tuple
from redis.asyncio import Redis
from common.const.settings import settings


# ── Cache key templates (모듈 공용 상수) ────────────────────────
# `get_team_scope` 등 외부에서도 키 존재 여부를 확인하므로 템플릿을 공개한다.
USER_TEAM_META_KEY = "rbac:ut:{uid}:{tid}"          # RBAC 메타 (권한 그룹/버전/admin 플래그)
GROUP_CODES_KEY    = "rbac:gc:{group_id}:v{version}"  # 그룹별 권한 코드 집합
TEAM_SCOPE_KEY     = "team:scope:{uid}:{tid}"        # 멤버십 확인 전용 캐시 (가벼운 플래그)


class RbacCacheService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_user_team_meta(self, user_id: int, team_id: int) -> Optional[dict]:
        key = USER_TEAM_META_KEY.format(uid=user_id, tid=team_id)
        raw = await self.redis.get(key)
        if raw:
            return json.loads(raw)
        return None

    async def set_user_team_meta(self, user_id: int, team_id: int, meta: dict) -> None:
        key = USER_TEAM_META_KEY.format(uid=user_id, tid=team_id)
        await self.redis.set(key, json.dumps(meta), ex=settings.RBAC_USER_TEAM_TTL)

    async def get_group_codes(self, group_id: int, version: int) -> Optional[Set[str]]:
        key = GROUP_CODES_KEY.format(group_id=group_id, version=version)
        raw = await self.redis.get(key)
        if raw:
            return set(json.loads(raw))
        return None

    async def set_group_codes(self, group_id: int, version: int, codes: Set[str]) -> None:
        key = GROUP_CODES_KEY.format(group_id=group_id, version=version)
        await self.redis.set(key, json.dumps(list(codes)), ex=settings.RBAC_GROUP_CODES_TTL)
