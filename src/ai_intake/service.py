# src/ai_intake/service.py
"""AI Intake — 환경변수로 선택된 provider 로 D/O 필드 추출.

- AI_INTAKE_PROVIDER="" → 비활성 (router 가 503)
- "gemini"            → GeminiProvider (무료 티어 가능)
- "anthropic"         → AnthropicProvider (종량제, 정확도 우선)
"""
from __future__ import annotations
from typing import Any

import structlog

from ai_intake.providers import IntakeProvider
from ai_intake.providers.anthropic_provider import AnthropicProvider
from ai_intake.providers.gemini_provider import GeminiProvider
from common.const.settings import settings

log = structlog.get_logger(__name__)


def _make_provider() -> IntakeProvider | None:
    """환경변수 기반 provider 인스턴스. 비활성 시 None."""
    name = (settings.AI_INTAKE_PROVIDER or "").lower().strip()
    model = settings.AI_INTAKE_MODEL or None
    if name == "gemini":
        if not settings.GEMINI_API_KEY:
            return None
        return GeminiProvider(settings.GEMINI_API_KEY, model=model)
    if name == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            return None
        return AnthropicProvider(settings.ANTHROPIC_API_KEY, model=model)
    return None


class AIIntakeService:
    """provider 추상화 wrapper. 비활성 provider 면 enabled=False."""

    def __init__(self) -> None:
        self._provider = _make_provider()

    @property
    def enabled(self) -> bool:
        return self._provider is not None

    @property
    def provider_name(self) -> str:
        return self._provider.name if self._provider else "disabled"

    async def extract_delivery_order(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """Provider 호출 + 표준 응답 (filename/size 메타 + fields/confidence)."""
        if self._provider is None:
            raise RuntimeError("AI Intake 비활성 (AI_INTAKE_PROVIDER 미설정)")

        log.info(
            "ai_intake.extract.start",
            provider=self._provider.name,
            filename=filename, size=len(file_bytes), content_type=content_type,
        )
        try:
            result = await self._provider.extract(
                file_bytes=file_bytes,
                content_type=content_type,
                filename=filename,
            )
        except Exception as e:
            log.error("ai_intake.provider_error", provider=self._provider.name, error=str(e))
            raise

        log.info(
            "ai_intake.extract.done",
            provider=self._provider.name,
            filename=filename,
            fields_count=len(result["fields"]),
            confidence=result["confidence"],
        )
        return {
            "filename": filename,
            "size_bytes": len(file_bytes),
            "fields": result["fields"],
            "confidence": result["confidence"],
            "provider": self._provider.name,
        }
