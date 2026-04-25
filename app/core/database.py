"""DB 엔진 (write/replica) + 세션 의존성.

- write: settings.database_url
- read:  settings.database_replica_url (미설정 시 write 풀과 동일)
- pool: pre_ping, lifo, recycle 1h
"""
from __future__ import annotations

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_use_lifo=True,
    pool_recycle=3600,
)

_replica_url = settings.database_replica_url
if _replica_url == settings.database_url:
    _read_engine = _engine
else:
    _read_engine = create_async_engine(
        _replica_url,
        pool_size=settings.db_replica_pool_size,
        max_overflow=settings.db_replica_max_overflow,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_recycle=3600,
    )

_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)
_ReadSessionLocal = async_sessionmaker(_read_engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """쓰기 세션. 라우터에서 트랜잭션 경계 관리."""
    async with _SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_db_replica() -> AsyncIterator[AsyncSession]:
    """읽기 전용 세션."""
    async with _ReadSessionLocal() as session:
        yield session


async def dispose_engines() -> None:
    await _engine.dispose()
    if _read_engine is not _engine:
        await _read_engine.dispose()
