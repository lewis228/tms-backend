# src/common/schemas/custom_field.py
from __future__ import annotations

from pydantic import BaseModel, Field


class CustomFieldValueSchema(BaseModel):
    """주문서별 커스텀 필드 값 (JSON 컬럼 아이템)."""
    name: str = Field(max_length=128)
    value: str = Field(default="", max_length=500)
