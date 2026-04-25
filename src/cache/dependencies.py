from __future__ import annotations
from redis.asyncio import Redis
from cache.redis_connection import write_redis, read_redis, redis_client, RedisClient


async def get_write_redis() -> Redis:
    return write_redis

async def get_read_redis() -> Redis:
    return read_redis

async def get_redis_client() -> RedisClient:
    return redis_client

async def get_redis() -> Redis:
    return write_redis
