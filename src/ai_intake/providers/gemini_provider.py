# src/ai_intake/providers/gemini_provider.py
"""Google Gemini vision provider — 무료 티어 (Flash) 사용 가능.

발급: aistudio.google.com → Get API key (카드 등록 불필요)
한도: Gemini 2.0 Flash 무료 → 분당 15회 / 일 1500회 / 분당 100만 토큰
"""
from __future__ import annotations
import structlog

from ai_intake.providers.base import (
    IntakeProvider, ExtractResult, SYSTEM_PROMPT, parse_response, media_type,
)

log = structlog.get_logger(__name__)


DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiProvider(IntakeProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY 가 비어있다")
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL

    async def extract(
        self, *, file_bytes: bytes, content_type: str, filename: str,
    ) -> ExtractResult:
        try:
            from google import genai
            from google.genai import types as gtypes
        except ImportError as e:
            raise RuntimeError(f"google-genai SDK 미설치: {e}") from e

        client = genai.Client(api_key=self._api_key)
        mt = media_type(content_type)

        log.info("gemini.extract.start", filename=filename, size=len(file_bytes), model=self._model)

        # genai 의 Part.from_bytes 로 이미지/PDF inline 첨부
        part = gtypes.Part.from_bytes(data=file_bytes, mime_type=mt)
        prompt = "위 D/O 에서 필드를 추출하세요."

        resp = await client.aio.models.generate_content(
            model=self._model,
            contents=[part, prompt],
            config=gtypes.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )

        raw_text = (resp.text or "").strip()
        return parse_response(raw_text)
