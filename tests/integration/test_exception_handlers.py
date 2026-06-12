# tests/integration/test_exception_handlers.py
"""전역 SQLAlchemy 예외 핸들러 — MySQL 에러코드 → HTTP 매핑 검증."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from common.exceptions.handlers import sqlalchemy_exception_handler


def _fake_request():
    req = MagicMock()
    req.url.path = "/api/v1/service-areas"
    req.method = "POST"
    req.headers = {}
    req.client = None
    return req


def _dbapi_exc(exc_cls, errno: int, msg: str):
    orig = Exception(errno, msg)
    orig.args = (errno, msg)
    return exc_cls(statement="INSERT ...", params=None, orig=orig)


@pytest.mark.asyncio
async def test_duplicate_entry_1062_maps_to_409():
    """동시 중복 생성 레이스(유니크 위반 1062) → 500 이 아니라 409 DUPLICATE_ENTRY."""
    exc = _dbapi_exc(IntegrityError, 1062, "Duplicate entry 'ZIP3-CA-902' for key ...")
    resp = await sqlalchemy_exception_handler(_fake_request(), exc)
    assert resp.status_code == 409
    body = json.loads(resp.body)
    assert body["error"]["code"] == "DUPLICATE_ENTRY"


@pytest.mark.asyncio
async def test_lock_and_timeout_mappings_unchanged():
    """기존 매핑 회귀 방지 — 1213(데드락)→409, 3024(시간초과)→504, 기타→500."""
    deadlock = _dbapi_exc(OperationalError, 1213, "Deadlock found")
    resp = await sqlalchemy_exception_handler(_fake_request(), deadlock)
    assert resp.status_code == 409
    assert json.loads(resp.body)["error"]["code"] == "DB_LOCK_CONFLICT"

    timeout = _dbapi_exc(OperationalError, 3024, "Query execution was interrupted")
    resp2 = await sqlalchemy_exception_handler(_fake_request(), timeout)
    assert resp2.status_code == 504

    unknown = _dbapi_exc(OperationalError, 9999, "???")
    resp3 = await sqlalchemy_exception_handler(_fake_request(), unknown)
    assert resp3.status_code == 500
    assert json.loads(resp3.body)["error"]["code"] == "DB_ERROR"
