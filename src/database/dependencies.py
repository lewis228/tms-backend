from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from database.mysql_connection import write_session_maker, read_session_maker


async def get_write_db() -> AsyncGenerator[AsyncSession, None]:
    async with write_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    async with read_session_maker() as session:
        try:
            yield session
        finally:
            pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with write_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
