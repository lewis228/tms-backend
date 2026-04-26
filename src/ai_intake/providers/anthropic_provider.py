# src/ai_intake/providers/anthropic_provider.py
"""Claude (Anthropic) vision provider — 종량제, 정확도 우선."""
from __future__ import annotations
import base64
import structlog

from ai_intake.providers.base import (
    IntakeProvider, ExtractResult, SYSTEM_PROMPT, parse_response, media_type,
)

log = structlog.get_logger(__name__)


DEFAULT_MODEL = "claude-opus-4-7"
MAX_TOKENS = 2000


class AnthropicProvider(IntakeProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 가 비어있다")
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL

    async def extract(
        self, *, file_bytes: bytes, content_type: str, filename: str,
    ) -> ExtractResult:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError(f"anthropic SDK 미설치: {e}") from e

        client = AsyncAnthropic(api_key=self._api_key)
        mt = media_type(content_type)
        b64 = base64.b64encode(file_bytes).decode("ascii")

        if mt == "application/pdf":
            content = [
                {"type": "document",
                 "source": {"type": "base64", "media_type": mt, "data": b64}},
                {"type": "text", "text": "위 D/O 에서 필드를 추출하세요."},
            ]
        else:
            content = [
                {"type": "image",
                 "source": {"type": "base64", "media_type": mt, "data": b64}},
                {"type": "text", "text": "위 D/O 에서 필드를 추출하세요."},
            ]

        log.info("anthropic.extract.start", filename=filename, size=len(file_bytes))
        resp = await client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        raw_text = ""
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                raw_text += getattr(block, "text", "")
        return parse_response(raw_text)
