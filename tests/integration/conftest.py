# tests/integration/conftest.py
"""Integration 테스트용 fixture.

테스트 DB: 항상 전용 DB `tms_test` (tests/conftest.py 가 DB_DATABASE 강제).
세션 시작 시 _prepare_test_db 가 (1) DB 없으면 생성 (2) alembic upgrade head 로
스키마 최신화 — dev DB(tms) 는 더 이상 건드리지 않는다.

격리 전략:
  - 각 테스트 함수 시작 전 모든 테이블 TRUNCATE (FK_CHECKS=0).
  - service 가 commit 호출하기 때문에 transactional rollback 패턴 사용 불가.
  - 따라서 명시적 truncate 가 가장 단순/확실.

Pool 전략:
  - 앱의 write_engine 은 prod-style pool (pool_pre_ping=True).
  - pytest-asyncio 가 매 테스트 새 event loop 를 만들어 pool 의 connection 이 죽은 loop 에 묶임 → ping 실패.
  - 테스트는 NullPool 로 매 connection 신규 생성 → loop 격리 OK.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import quote_plus

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# common.model.models_registry 를 import 해서 모든 모델이 metadata 에 등록되도록 함
import common.model.models_registry  # noqa: F401
from common.model.base_model import Base
from database.mysql_connection import build_mysql_dsn
from common.const.settings import settings


# prod/dev 데이터 보호 — 전용 테스트 DB 만 TRUNCATE 허용.
_TEST_DB_ALLOWLIST = frozenset({"tms_test"})

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_test_engine():
    dsn = build_mysql_dsn(settings.DB_HOST)
    return create_async_engine(dsn, echo=False, poolclass=NullPool)


async def _create_database_if_missing() -> None:
    """서버 레벨 접속(DB 미지정)으로 tms_test 생성."""
    host = settings.DB_HOST
    if host in ("localhost", "::1"):
        host = "127.0.0.1"
    server_dsn = (
        f"mysql+aiomysql://{settings.DB_USERNAME}:{quote_plus(settings.DB_PASSWORD)}"
        f"@{host}:{settings.DB_PORT}/?charset=utf8mb4"
    )
    engine = create_async_engine(server_dsn, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{settings.DB_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            ))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """세션 1회 — tms_test 생성 + alembic upgrade head 로 스키마 최신화.

    alembic 은 subprocess 로 실행: env.py 가 settings(env var) 에서 URL 을 만들고,
    이 프로세스의 DB_DATABASE=tms_test 가 상속되므로 정확히 테스트 DB 만 마이그레이션된다.
    (동기 픽스처 + asyncio.run — pytest-asyncio 세션 스코프 루프 이슈 회피)
    """
    if settings.DB_DATABASE not in _TEST_DB_ALLOWLIST:
        raise RuntimeError(
            f"테스트 DB 가 전용 DB 가 아닙니다: '{settings.DB_DATABASE}' "
            f"(허용 = {sorted(_TEST_DB_ALLOWLIST)}). tests/conftest.py 가 "
            "DB_DATABASE 를 강제하는지 확인하세요."
        )
    asyncio.run(_create_database_if_missing())
    # DATABASE_URL 이 셸에 있으면 migrations/env.py 가 settings 보다 그걸 우선시해
    # tms_test 강제를 우회한다 — subprocess env 에서 제거해 테스트 DB 만 마이그레이션.
    sub_env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_REPO_ROOT, env=sub_env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"테스트 DB(alembic upgrade head) 실패:\n{proc.stdout}\n{proc.stderr}"
        )


@pytest.fixture(autouse=True)
def _mute_realtime_publish(monkeypatch):
    """테스트에서 WS 이벤트 발행 무력화.

    realtime.service.publish 는 전역 redis 클라이언트를 쓰는데, pytest-asyncio 가
    테스트마다 새 이벤트 루프를 만들므로 발행이 만든 커넥션이 죽은 루프에 귀속되어
    이후 테스트의 redis 사용(세션 미들웨어 등)을 오염시킨다. emit_entity_event 는
    모듈 전역 publish 를 호출 시점에 조회하므로 여기를 패치하면 전부 무력화된다.
    """
    import realtime.emit as _emit_mod

    async def _noop(event, *, db=None):  # noqa: ARG001
        return 0

    monkeypatch.setattr(_emit_mod, "publish", _noop)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """함수 스코프 — 테스트마다 신규 엔진 + 테이블 truncate."""
    if settings.DB_DATABASE not in _TEST_DB_ALLOWLIST:
        raise RuntimeError(
            f"통합 테스트 DB 화이트리스트 위반: '{settings.DB_DATABASE}'. "
            f"허용 목록 = {sorted(_TEST_DB_ALLOWLIST)}. "
            f"실수로 prod DB 를 truncate 하지 않게 차단됨. "
            f"테스트 의도면 conftest.py 의 _TEST_DB_ALLOWLIST 에 추가."
        )
    engine = _make_test_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(text(f"TRUNCATE TABLE `{table.name}`"))
            await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as session:
            yield session
    finally:
        await engine.dispose()
