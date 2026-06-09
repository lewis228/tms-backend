# src/rate_import/schemas/request.py
from __future__ import annotations
from pydantic import Field
from common.schemas.base import RequestSchema


class CsvImportRequest(RequestSchema):
    """CSV 텍스트 import (dry_run 으로 검증/미리보기)."""
    csv: str = Field(min_length=1)
    dry_run: bool = False
