# src/cache/redis_connection.py
"""
Redis 연결 설정 (읽기/쓰기 분리 지원)

개발 환경: REDIS_HOST만 설정 → 단일 Redis 사용
운영 환경: REDIS_WRITE_HOST + REDIS_READ_HOST 설정 → 분리
"""
from __future__ import annotations
from redis.asyncio import Redis, ConnectionPool
from common.const.settings import settings


def _create_pool(host: str, port: int, db: int, password: str | None, max_connections: int = 10) -> ConnectionPool:
    """Redis ConnectionPool 생성 헬퍼"""
    return ConnectionPool(
        host=host,
        port=port,
        db=db,
        password=password or None,
        max_connections=max_connections,
        decode_responses=True,
    )


# ─────────────────────────────────────────────────────────
# 환경에 따른 Redis 클라이언트 생성
# ─────────────────────────────────────────────────────────

if settings.is_redis_read_write_split:
    #  운영 환경: 읽기/쓰기 분리
    write_pool = _create_pool(
        host=settings.REDIS_WRITE_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        max_connections=10,  # 쓰기는 적게
    )
    read_pool = _create_pool(
        host=settings.REDIS_READ_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        max_connections=50,  # 읽기는 많이
    )
    write_redis = Redis(connection_pool=write_pool)
    read_redis = Redis(connection_pool=read_pool)
else:
    #  개발 환경: 단일 Redis (REDIS_HOST 사용)
    single_pool = _create_pool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        max_connections=20,
    )
    single_redis = Redis(connection_pool=single_pool)
    
    # 읽기/쓰기 모두 같은 Redis 사용
    write_redis = single_redis
    read_redis = single_redis


# ─────────────────────────────────────────────────────────
# RedisClient 래퍼 클래스 (선택적 사용)
# ─────────────────────────────────────────────────────────

class RedisClient:
    """
    읽기/쓰기를 자동 분리하는 Redis 래퍼 클래스
    
    사용 예:
        client = RedisClient()
        await client.set("key", "value")  # → write_redis
        await client.get("key")           # → read_redis
    """
    
    def __init__(self, write: Redis = None, read: Redis = None):
        self._write = write or write_redis
        self._read = read or read_redis
    
    # ─── 쓰기 작업 (Primary) ───
    async def set(self, key: str, value: str, ex: int = None, px: int = None, nx: bool = False, xx: bool = False):
        return await self._write.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
    
    async def setex(self, key: str, seconds: int, value: str):
        return await self._write.setex(key, seconds, value)
    
    async def setnx(self, key: str, value: str):
        return await self._write.setnx(key, value)
    
    async def delete(self, *keys):
        return await self._write.delete(*keys)
    
    async def expire(self, key: str, seconds: int):
        return await self._write.expire(key, seconds)
    
    async def incr(self, key: str):
        return await self._write.incr(key)
    
    async def decr(self, key: str):
        return await self._write.decr(key)
    
    async def hset(self, name: str, key: str = None, value: str = None, mapping: dict = None):
        return await self._write.hset(name, key, value, mapping=mapping)
    
    async def hdel(self, name: str, *keys):
        return await self._write.hdel(name, *keys)
    
    async def sadd(self, name: str, *values):
        return await self._write.sadd(name, *values)
    
    async def srem(self, name: str, *values):
        return await self._write.srem(name, *values)
    
    async def lpush(self, name: str, *values):
        return await self._write.lpush(name, *values)
    
    async def rpush(self, name: str, *values):
        return await self._write.rpush(name, *values)
    
    async def lpop(self, name: str):
        return await self._write.lpop(name)
    
    async def rpop(self, name: str):
        return await self._write.rpop(name)
    
    # ─── 읽기 작업 (Replica) ───
    async def get(self, key: str):
        return await self._read.get(key)
    
    async def mget(self, *keys):
        return await self._read.mget(*keys)
    
    async def exists(self, *keys):
        return await self._read.exists(*keys)
    
    async def ttl(self, key: str):
        return await self._read.ttl(key)
    
    async def keys(self, pattern: str = "*"):
        return await self._read.keys(pattern)
    
    async def hget(self, name: str, key: str):
        return await self._read.hget(name, key)
    
    async def hgetall(self, name: str):
        return await self._read.hgetall(name)
    
    async def hmget(self, name: str, *keys):
        return await self._read.hmget(name, *keys)
    
    async def sismember(self, name: str, value: str):
        return await self._read.sismember(name, value)
    
    async def smembers(self, name: str):
        return await self._read.smembers(name)
    
    async def lrange(self, name: str, start: int, end: int):
        return await self._read.lrange(name, start, end)
    
    async def llen(self, name: str):
        return await self._read.llen(name)
    
    # ─── Replication Lag 회피용 (Primary에서 직접 읽기) ───
    async def get_from_primary(self, key: str):
        """방금 쓴 데이터를 즉시 읽어야 할 때 사용"""
        return await self._write.get(key)
    
    async def exists_on_primary(self, *keys):
        """Primary에서 존재 여부 확인"""
        return await self._write.exists(*keys)


# 싱글톤 인스턴스
redis_client = RedisClient()


# ─────────────────────────────────────────────────────────
# 레거시 호환용 (기존 get_redis 사용 코드용)
# ─────────────────────────────────────────────────────────

# 기존 코드 호환: get_redis()는 write_redis 반환 (안전한 기본값)
redis = write_redis