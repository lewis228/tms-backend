# src/common/middleware/rate_limit.py
"""
Redis 기반 Rate Limiter (FastAPI 의존성)

사용법:
    @router.get("/endpoint")
    async def handler(
        _: None = Depends(rate_limit(max_calls=30, period=60)),
    ):
        ...
"""
from __future__ import annotations

from fastapi import Depends, Request
from redis.asyncio import Redis

from cache.dependencies import get_write_redis
from common.exceptions.base import AppException


def rate_limit(*, max_calls: int, period: int):
    """
    IP 기반 Rate Limiter 의존성 팩토리.

    Args:
        max_calls: 허용 최대 호출 횟수
        period: 시간 윈도우 (초)
    """

    async def _check(
        request: Request,
        redis: Redis = Depends(get_write_redis),
    ) -> None:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        key = f"rate_limit:{path}:{client_ip}"

        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, period)

        if current > max_calls:
            raise AppException(
                code="RATE_LIMIT_EXCEEDED",
                message="요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
                status_code=429,
            )

    return _check
