# database/mysql_connection.py
"""
MySQL 연결 설정 (K8s 읽기/쓰기 분리 지원)

개발 환경 (ENV=development):
  - 단일 엔진 사용 (write_engine = read_engine)

운영 환경 (ENV=production + DB_WRITE_HOST/DB_READ_HOST 설정):
  - write_engine: mysql-primary (쓰기 전용)
  - read_engine: mysql-read (읽기 전용, Replica로 분산)

 글로벌 서비스 대응:
  - 모든 세션에서 time_zone = '+00:00' (UTC) 설정
  - 저장/전송은 UTC, 표시는 클라이언트에서 로컬 변환
"""
from __future__ import annotations
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from urllib.parse import quote_plus

from common.const.settings import settings
from database.timed_session import TimedAsyncSession


def build_mysql_dsn(host: str) -> str:
    """MySQL DSN 생성"""
    # localhost IPv6 이슈 회피
    if host in ("localhost", "::1"):
        host = "127.0.0.1"
    
    user = quote_plus(settings.DB_USERNAME)
    pwd = settings.DB_PASSWORD or ""
    auth = f"{user}:{quote_plus(pwd)}@" if pwd else f"{user}@"
    
    return f"mysql+aiomysql://{auth}{host}:{settings.DB_PORT}/{settings.DB_DATABASE}?charset=utf8mb4"


def _create_engine(dsn: str, *, pool_size: int = 10, max_overflow: int = 20) -> AsyncEngine:
    """엔진 생성 공통 로직"""
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
        connect_args={
            "connect_timeout": 5,
        },
    )


def _setup_session_settings(engine: AsyncEngine) -> None:
    """
    세션 설정 이벤트 등록
    - UTC 타임존 설정 (글로벌 서비스 대응)
    - 쿼리 타임아웃 설정
    - 락 대기 타임아웃 설정
    """
    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_conn, conn_record):
        cur = dbapi_conn.cursor()
        try:
            #  UTC 타임존 설정 (글로벌 서비스 필수)
            # 모든 DATETIME 연산이 UTC 기준으로 수행됨
            cur.execute("SET time_zone = '+00:00'")
            
            # 쿼리 실행 타임아웃 (밀리초)
            if int(settings.DB_MAX_EXEC_MS) > 0:
                cur.execute(f"SET SESSION MAX_EXECUTION_TIME={int(settings.DB_MAX_EXEC_MS)}")
            
            # InnoDB 락 대기 타임아웃 (초)
            if int(settings.DB_LOCK_WAIT_TIMEOUT) > 0:
                cur.execute(f"SET SESSION innodb_lock_wait_timeout={int(settings.DB_LOCK_WAIT_TIMEOUT)}")
        finally:
            cur.close()


# ===== 엔진 생성 =====
if settings.is_db_read_write_split:
    # 운영 환경: 읽기/쓰기 분리
    write_dsn = build_mysql_dsn(settings.DB_WRITE_HOST)
    read_dsn = build_mysql_dsn(settings.DB_READ_HOST)
    
    write_engine = _create_engine(
        write_dsn,
        pool_size=settings.DB_WRITE_POOL_SIZE,
        max_overflow=settings.DB_WRITE_MAX_OVERFLOW,
    )
    read_engine = _create_engine(
        read_dsn,
        pool_size=settings.DB_READ_POOL_SIZE,
        max_overflow=settings.DB_READ_MAX_OVERFLOW,
    )
    
    _setup_session_settings(write_engine)
    _setup_session_settings(read_engine)
    
else:
    # 개발 환경: 단일 엔진
    single_dsn = build_mysql_dsn(settings.DB_HOST)
    
    write_engine = _create_engine(
        single_dsn,
        pool_size=settings.DB_WRITE_POOL_SIZE,
        max_overflow=settings.DB_WRITE_MAX_OVERFLOW,
    )
    read_engine = write_engine  # 같은 엔진 참조
    
    _setup_session_settings(write_engine)


# ===== 레거시 호환 =====
# 기존 코드에서 async_engine을 사용하는 경우 대비
async_engine = write_engine
DATABASE_CONN = build_mysql_dsn(
    settings.DB_WRITE_HOST if settings.is_db_read_write_split else settings.DB_HOST
)


# ===== Session Factory =====
write_session_maker = sessionmaker(
    bind=write_engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    class_=TimedAsyncSession,
)

read_session_maker = sessionmaker(
    bind=read_engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    class_=TimedAsyncSession,
)

# 레거시 호환 (기존 코드에서 async_session_maker 사용하는 경우)
async_session_maker = write_session_maker