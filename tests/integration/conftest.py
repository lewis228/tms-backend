# tests/integration/conftest.py
"""Integration 테스트용 fixture.

전제: alembic upgrade head 가 사전에 실행됨 (pytest 실행 전 또는 CI 단계).

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

from typing import AsyncIterator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# common.model.models_registry 를 import 해서 모든 모델이 metadata 에 등록되도록 함
import common.model.models_registry  # noqa: F401
from common.model.base_model import Base
from database.mysql_connection import build_mysql_dsn
from common.const.settings import settings


# prod 데이터 보호 — 화이트리스트에 있는 DB 이름만 TRUNCATE 허용.
# 신규 DB 추가 시 명시적으로 여기 등록해야 통과.
_TEST_DB_ALLOWLIST = frozenset({"tms", "tms_test"})


def _make_test_engine():
    dsn = build_mysql_dsn(settings.DB_HOST)
    return create_async_engine(dsn, echo=False, poolclass=NullPool)


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
