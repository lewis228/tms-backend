# database/timed_session.py
"""
타임아웃이 적용된 AsyncSession
(기존 코드 유지 - 변경 없음)
"""
from __future__ import annotations
import asyncio
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select, Insert, Update, Delete
from sqlalchemy.sql.elements import TextClause
from common.const.settings import settings


class TimedAsyncSession(AsyncSession):
    """
    쿼리 타입별 타임아웃이 자동 적용되는 AsyncSession
    
    - SELECT: read_timeout 적용
    - INSERT/UPDATE/DELETE: write_timeout 적용
    """
    read_timeout: float = float(settings.DB_READ_TIMEOUT)
    write_timeout: float = float(settings.DB_WRITE_TIMEOUT)

    def _pick_timeout(self, statement: Any) -> float:
        """쿼리 타입에 따라 타임아웃 선택"""
        try:
            if isinstance(statement, Select):
                return self.read_timeout
            if isinstance(statement, (Insert, Update, Delete)):
                return self.write_timeout
            if isinstance(statement, TextClause):
                sql = statement.text.lstrip().upper()
                if sql.startswith("SELECT"):
                    return self.read_timeout
                return self.write_timeout
        except Exception:
            pass
        return self.write_timeout

    async def execute(self, statement: Any, *args, **kwargs):
        timeout = self._pick_timeout(statement)
        return await asyncio.wait_for(
            super().execute(statement, *args, **kwargs),
            timeout=timeout
        )

    async def scalars(self, statement: Any, *args, **kwargs):
        timeout = self._pick_timeout(statement)
        return await asyncio.wait_for(
            super().scalars(statement, *args, **kwargs),
            timeout=timeout
        )

    async def commit(self):
        return await asyncio.wait_for(super().commit(), timeout=self.write_timeout)

    async def flush(self):
        return await asyncio.wait_for(super().flush(), timeout=self.write_timeout)