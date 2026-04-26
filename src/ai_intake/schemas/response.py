# src/ai_intake/schemas/response.py
from __future__ import annotations
from typing import Any
from common.schemas.base import ResponseSchema


class AIIntakeExtractResponse(ResponseSchema):
    filename: str
    size_bytes: int
    fields: dict[str, Any]
    confidence: float
    provider: str = ""    # "gemini" | "anthropic" — 프론트 표시용
