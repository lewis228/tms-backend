# database/mysql_connection.py
from __future__ import annotations
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from urllib.parse import quote_plus

from common.const.settings import settings
from database.timed_session import TimedAsyncSession


def build_mysql_dsn(host: str) -> str:
    if host in ("localhost", "::1"):
        host = "127.0.0.1"
    user = quote_plus(settings.DB_USERNAME)
    pwd = settings.DB_PASSWORD or ""
    auth = f"{user}:{quote_plus(pwd)}@" if pwd else f"{user}@"
    return f"mysql+aiomysql://{auth}{host}:{settings.DB_PORT}/{settings.DB_DATABASE}?charset=utf8mb4"


def _create_engine(dsn: str, *, pool_size: int = 10, max_overflow: int = 20) -> AsyncEngine:
    return create_async_engine(
        dsn,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
        pool_use_lifo=True,
        isolation_level="READ COMMITTED",
        connect_args={"connect_timeout": 5},
    )


def _setup_session_settings(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_conn, conn_record):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("SET time_zone = '+00:00'")
            if int(settings.DB_MAX_EXEC_MS) > 0:
                cur.execute(f"SET SESSION MAX_EXECUTION_TIME={int(settings.DB_MAX_EXEC_MS)}")
            if int(settings.DB_LOCK_WAIT_TIMEOUT) > 0:
                cur.execute(f"SET SESSION innodb_lock_wait_timeout={int(settings.DB_LOCK_WAIT_TIMEOUT)}")
        finally:
            cur.close()


if settings.is_db_read_write_split:
    write_dsn = build_mysql_dsn(settings.DB_WRITE_HOST)
    read_dsn = build_mysql_dsn(settings.DB_READ_HOST)
    write_engine = _create_engine(write_dsn, pool_size=settings.DB_WRITE_POOL_SIZE, max_overflow=settings.DB_WRITE_MAX_OVERFLOW)
    read_engine = _create_engine(read_dsn, pool_size=settings.DB_READ_POOL_SIZE, max_overflow=settings.DB_READ_MAX_OVERFLOW)
    _setup_session_settings(write_engine)
    _setup_session_settings(read_engine)
else:
    single_dsn = build_mysql_dsn(settings.DB_HOST)
    write_engine = _create_engine(single_dsn, pool_size=settings.DB_WRITE_POOL_SIZE, max_overflow=settings.DB_WRITE_MAX_OVERFLOW)
    read_engine = write_engine
    _setup_session_settings(write_engine)

async_engine = write_engine
DATABASE_CONN = build_mysql_dsn(
    settings.DB_WRITE_HOST if settings.is_db_read_write_split else settings.DB_HOST
)

write_session_maker = sessionmaker(bind=write_engine, expire_on_commit=False, autoflush=False, autocommit=False, class_=TimedAsyncSession)
read_session_maker = sessionmaker(bind=read_engine, expire_on_commit=False, autoflush=False, autocommit=False, class_=TimedAsyncSession)
async_session_maker = write_session_maker
