from __future__ import annotations
from datetime import datetime, timezone
from fastapi import Depends, Response
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from cache.redis_connection import redis_client
from common.exceptions.base import AppException

PLAN_LIMITS = {
    "free": 100,
    "basic": 1000,
    "pro": 10000,
}

# TTL covers the rolling 30-day window so the Usage dashboard can plot a
# full month of historical API calls by reading the daily counters back
# out of Redis. The counter reset itself is still daily — keys are
# `rate_limit:{team}:{YYYY-MM-DD}` so the day-of enforcement is unaffected.
RATE_LIMIT_TTL = 30 * 86400


async def rate_limit(
    response: Response,
    auth: AuthResult = Depends(jwt_or_api_key),
):
    # Only API-key callers are rate-limited — JWT (web app) traffic is
    # governed by UI throttling. If team_id is missing (e.g. shouldn't
    # happen for api_key path, but defend anyway) we let the request
    # through rather than falsely blocking.
    if auth.auth_type == "jwt":
        return
    if auth.team_id is None:
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"rate_limit:{auth.team_id}:{today}"
    limit = PLAN_LIMITS.get(auth.plan, PLAN_LIMITS["free"])

    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, RATE_LIMIT_TTL)

    remaining = max(0, limit - count)

    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = today

    if count > limit:
        raise AppException(
            code="RATE_LIMIT_EXCEEDED",
            message=f"일일 API 호출 제한({limit}회)을 초과했습니다. plan 업그레이드를 고려하세요.",
            status_code=429,
        )
