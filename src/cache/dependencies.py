# src/cache/dependencies.py
"""
Redis 의존성 주입 (읽기/쓰기 분리 지원)

사용법:
    # 읽기 작업 (GET, EXISTS 등)
    redis: Redis = Depends(get_read_redis)
    
    # 쓰기 작업 (SET, DELETE 등)
    redis: Redis = Depends(get_write_redis)
    
    # 래퍼 클래스 (자동 분리)
    client: RedisClient = Depends(get_redis_client)
    
    # 레거시 호환 (write와 동일)
    redis: Redis = Depends(get_redis)
"""
from __future__ import annotations
from redis.asyncio import Redis

from cache.redis_connection import (
    write_redis,
    read_redis,
    redis_client,
    RedisClient,
)


# ─────────────────────────────────────────────────────────
# 쓰기 전용 (SET, DELETE, EXPIRE 등)
# ─────────────────────────────────────────────────────────
async def get_write_redis() -> Redis:
    """
    쓰기 작업용 Redis 클라이언트
    
    운영 환경: redis-primary (Primary)
    개발 환경: localhost (단일)
    """
    return write_redis


# ─────────────────────────────────────────────────────────
# 읽기 전용 (GET, EXISTS, KEYS 등)
# ─────────────────────────────────────────────────────────
async def get_read_redis() -> Redis:
    """
    읽기 작업용 Redis 클라이언트
    
    운영 환경: redis-read (Replica 분산)
    개발 환경: localhost (단일)
    """
    return read_redis


# ─────────────────────────────────────────────────────────
# 래퍼 클래스 (읽기/쓰기 자동 분리)
# ─────────────────────────────────────────────────────────
async def get_redis_client() -> RedisClient:
    """
    RedisClient 래퍼 인스턴스
    
    사용 예:
        client = Depends(get_redis_client)
        await client.set("key", "value")  # 자동으로 write_redis 사용
        await client.get("key")           # 자동으로 read_redis 사용
    """
    return redis_client


# ─────────────────────────────────────────────────────────
# 레거시 호환 (기존 get_redis 사용 코드용)
# ─────────────────────────────────────────────────────────
async def get_redis() -> Redis:
    """
    레거시 호환용 - write_redis 반환
    
    ⚠️ 신규 코드에서는 get_write_redis 또는 get_read_redis 사용 권장
    """
    return write_redis