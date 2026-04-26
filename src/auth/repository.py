# auth/repository.py
from __future__ import annotations
from typing import Optional
import time
from redis.asyncio import Redis


# Redis 키 네임 규칙을 상수로 모아 관리
REFRESH_KEY = "refresh:{sid}"
SESSION_KEY = "sess:{sid}"
ACCESS_BLACKLIST_KEY = "bl:a:{jti}"


class AuthRepository:
    """인증/세션 관련 Redis 접근 레이어.
    - 세션/리프레시 토큰 저장/삭제
    - 액세스 토큰 블랙리스트 관리
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def save_refresh_token(self, sid: str, refresh_token: str, ttl: int) -> None:
        await self.redis.set(REFRESH_KEY.format(sid=sid), refresh_token, ex=ttl)

    async def get_refresh_token(self, sid: str) -> Optional[str]:
        token = await self.redis.get(REFRESH_KEY.format(sid=sid))
        return token.decode() if isinstance(token, (bytes, bytearray)) else token

    async def delete_refresh_token(self, sid: str) -> None:
        await self.redis.delete(REFRESH_KEY.format(sid=sid))

    async def is_blacklisted(self, jti: str) -> bool:
        return await self.redis.exists(ACCESS_BLACKLIST_KEY.format(jti=jti)) == 1

    async def blacklist_token(self, jti: str, exp_epoch: int) -> None:
        """만료 시각(exp)에 맞춘 TTL로 블랙리스트 저장"""
        ttl = exp_epoch - int(time.time())
        if ttl > 0:
            await self.redis.setex(ACCESS_BLACKLIST_KEY.format(jti=jti), ttl, "1")
