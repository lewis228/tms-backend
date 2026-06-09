# src/rate_import/schemas/response.py
from __future__ import annotations
from typing import List
from common.schemas.base import ResponseSchema


class ImportRowError(ResponseSchema):
    row: int          # 1-based 데이터 행 번호
    message: str


class CsvImportReport(ResponseSchema):
    """import 결과 리포트. errors 가 있으면 아무것도 적용되지 않음(전체 실패)."""
    ok: bool
    total: int
    applied: int
    dry_run: bool = False
    errors: List[ImportRowError] = []
