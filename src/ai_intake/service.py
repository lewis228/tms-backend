# src/ai_intake/service.py
"""AI Intake — Claude API 로 PDF/이미지에서 D/O 필드 추출.

settings.ANTHROPIC_API_KEY 가 비어있으면 endpoint 가 503 반환.
"""
from __future__ import annotations
from typing import Any
import structlog

from common.const.settings import settings

log = structlog.get_logger(__name__)


class AIIntakeService:
    """단순 wrapper. 실제 OCR / 필드 추출 로직은 추후 정교화."""

    def __init__(self) -> None:
        self._enabled = bool(getattr(settings, "ANTHROPIC_API_KEY", ""))

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def extract_delivery_order(self, *, file_bytes: bytes, filename: str) -> dict[str, Any]:
        """파일에서 D/O 필드 추출. 미구현 — placeholder.

        실 구현:
        1. Claude API 호출 (vision)
        2. 응답 파싱 → 필드 dict + confidence
        """
        if not self._enabled:
            raise RuntimeError("ANTHROPIC_API_KEY 미설정 — AI Intake 비활성")
        log.info("ai_intake.extract", filename=filename, size=len(file_bytes))
        # TODO: Claude API 호출
        return {
            "filename": filename,
            "size_bytes": len(file_bytes),
            "fields": {},
            "confidence": 0.0,
            "_note": "stub — Claude 호출 미구현",
        }
