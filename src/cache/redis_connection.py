from __future__ import annotations
from redis.asyncio import Redis, ConnectionPool
from common.const.settings import settings


def _create_pool(host: str, port: int, db: int, password: str | None, max_connections: int = 10) -> ConnectionPool:
    kwargs: dict = dict(
        host=host, port=port, db=db, password=password or None,
        max_connections=max_connections, decode_responses=True,
    )
    if settings.REDIS_SSL:
        # AWS ElastiCache (자체 서명 인증서) → CERT_NONE
        from redis.asyncio.connection import SSLConnection
        kwargs["connection_class"] = SSLConnection
        kwargs["ssl_cert_reqs"] = None
    return ConnectionPool(**kwargs)


if settings.is_redis_read_write_split:
    write_pool = _create_pool(host=settings.REDIS_WRITE_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD, max_connections=10)
    read_pool = _create_pool(host=settings.REDIS_READ_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD, max_connections=50)
    write_redis = Redis(connection_pool=write_pool)
    read_redis = Redis(connection_pool=read_pool)
else:
    single_pool = _create_pool(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, password=settings.REDIS_PASSWORD, max_connections=20)
    single_redis = Redis(connection_pool=single_pool)
    write_redis = single_redis
    read_redis = single_redis


class RedisClient:
    def __init__(self, write: Redis = None, read: Redis = None):
        self._write = write or write_redis
        self._read = read or read_redis

    # Write operations
    async def set(self, key, value, ex=None, px=None, nx=False, xx=False):
        return await self._write.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
    async def setex(self, key, seconds, value):
        return await self._write.setex(key, seconds, value)
    async def setnx(self, key, value):
        return await self._write.setnx(key, value)
    async def delete(self, *keys):
        return await self._write.delete(*keys)
    async def expire(self, key, seconds):
        return await self._write.expire(key, seconds)
    async def incr(self, key):
        return await self._write.incr(key)
    async def decr(self, key):
        return await self._write.decr(key)
    async def hset(self, name, key=None, value=None, mapping=None):
        return await self._write.hset(name, key, value, mapping=mapping)
    async def hdel(self, name, *keys):
        return await self._write.hdel(name, *keys)
    async def sadd(self, name, *values):
        return await self._write.sadd(name, *values)
    async def srem(self, name, *values):
        return await self._write.srem(name, *values)
    async def lpush(self, name, *values):
        return await self._write.lpush(name, *values)
    async def rpush(self, name, *values):
        return await self._write.rpush(name, *values)
    async def lpop(self, name):
        return await self._write.lpop(name)
    async def rpop(self, name):
        return await self._write.rpop(name)

    # Read operations
    async def get(self, key):
        return await self._read.get(key)
    async def mget(self, *keys):
        return await self._read.mget(*keys)
    async def exists(self, *keys):
        return await self._read.exists(*keys)
    async def ttl(self, key):
        return await self._read.ttl(key)
    async def keys(self, pattern="*"):
        return await self._read.keys(pattern)
    async def hget(self, name, key):
        return await self._read.hget(name, key)
    async def hgetall(self, name):
        return await self._read.hgetall(name)
    async def hmget(self, name, *keys):
        return await self._read.hmget(name, *keys)
    async def sismember(self, name, value):
        return await self._read.sismember(name, value)
    async def smembers(self, name):
        return await self._read.smembers(name)
    async def lrange(self, name, start, end):
        return await self._read.lrange(name, start, end)
    async def llen(self, name):
        return await self._read.llen(name)

    # Primary reads (bypass replication lag)
    async def get_from_primary(self, key):
        return await self._write.get(key)
    async def exists_on_primary(self, *keys):
        return await self._write.exists(*keys)


redis_client = RedisClient()
redis = write_redis
