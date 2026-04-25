# src/common/lifecycle/startup_check.py
from __future__ import annotations
import structlog
from sqlalchemy import text
from redis.exceptions import RedisError

from database.mysql_connection import async_session_maker
from cache.redis_connection import redis

logger = structlog.get_logger(__name__)

async def test_db_connection():
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        logger.info("db_connected")
    except Exception:
        logger.critical("db_connection_failed")
        raise

async def test_redis_connection():
    try:
        # decode_responses=True이므로 문자열로 비교
        await redis.set("__ping__", "pong", ex=5)
        result = await redis.get("__ping__")
        if result != "pong":  # ← b"pong" → "pong" 으로 변경!
            raise RedisError("invalid_redis_response")
        logger.info("redis_connected")
    except Exception as e:
        logger.critical("redis_connection_failed", error=str(e))
        raise
