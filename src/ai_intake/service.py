# src/ai_intake/service.py
"""AI Intake — Claude API (vision) 로 PDF/이미지에서 D/O 필드 추출.

settings.ANTHROPIC_API_KEY 가 비어있으면 endpoint 가 503 반환.
"""
from __future__ import annotations
import base64
import json
import re
from typing import Any
import structlog

from common.const.settings import settings

log = structlog.get_logger(__name__)


# 추출 대상 필드 — D/O 의 주요 컬럼.
_EXTRACT_FIELDS = [
    "bl_number", "booking_number", "reference",
    "container_number", "container_size", "container_type",
    "chassis_number",
    "eta", "pickup_appointment", "delivery_appointment", "return_appointment",
    "demurrage_lfd", "detention_lfd",
]

_SYSTEM_PROMPT = """당신은 운송 D/O (Delivery Order) 문서 OCR 전문 모델입니다.
첨부된 PDF/이미지에서 다음 필드를 추출해 JSON 으로 반환하세요.

필드:
- bl_number (B/L 번호, str)
- booking_number (Booking 번호, str)
- reference (Reference, str)
- container_number (^[A-Z]{4}[0-9]{7}$, str)
- container_size (20GP/40GP/40HC/40OT/45HC/20RF/40RF, str)
- container_type (DRY/RF/OT 등, str)
- chassis_number (str)
- eta (ISO 8601 datetime, str)
- pickup_appointment (ISO 8601 datetime, str)
- delivery_appointment (ISO 8601 datetime, str)
- return_appointment (ISO 8601 datetime, str)
- demurrage_lfd (ISO 8601 date, str)
- detention_lfd (ISO 8601 date, str)

규칙:
- 명확하지 않은 필드는 null.
- 추출에 자신 있는 정도를 0.0 ~ 1.0 confidence 로 평가.
- 응답은 반드시 JSON 객체 1개만. 마크다운 fence 없이.
  형식: {"fields": {...}, "confidence": 0.0}
"""


class AIIntakeService:
    """Claude vision 호출 wrapper. ANTHROPIC_API_KEY 없으면 enabled=False."""

    MODEL = "claude-opus-4-7"  # 정확도 우선
    MAX_TOKENS = 2000

    def __init__(self) -> None:
        self._api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
        self._enabled = bool(self._api_key)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def _media_type(content_type: str) -> str:
        """Claude API media_type 매핑."""
        ct = (content_type or "").lower()
        if ct in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            return ct
        if ct == "image/heic":
            return "image/jpeg"   # heic 는 직접 미지원 → 호출자가 변환 권장
        if ct == "application/pdf":
            return "application/pdf"
        # 기본값
        return "image/jpeg"

    async def extract_delivery_order(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """Claude API 로 D/O 필드 추출.

        반환: {filename, size_bytes, fields: dict, confidence: float}
        호출 실패 시 상위 router 가 처리 (HTTPException 으로 변환 권장).
        """
        if not self._enabled:
            raise RuntimeError("ANTHROPIC_API_KEY 미설정 — AI Intake 비활성")

        log.info("ai_intake.extract.start",
                 filename=filename, size=len(file_bytes), content_type=content_type)

        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError(f"anthropic SDK 미설치: {e}") from e

        client = AsyncAnthropic(api_key=self._api_key)
        media_type = self._media_type(content_type)
        b64 = base64.b64encode(file_bytes).decode("ascii")

        # Claude vision message (PDF 는 source.type="document", 이미지는 "image")
        if media_type == "application/pdf":
            content = [
                {"type": "document",
                 "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": "위 D/O 에서 필드를 추출하세요."},
            ]
        else:
            content = [
                {"type": "image",
                 "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": "위 D/O 에서 필드를 추출하세요."},
            ]

        try:
            resp = await client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )
        except Exception as e:
            log.error("ai_intake.claude_error", error=str(e))
            raise

        # 응답 텍스트 → JSON 파싱
        raw_text = ""
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                raw_text += getattr(block, "text", "")

        try:
            parsed = json.loads(self._strip_fences(raw_text))
            fields_dict = parsed.get("fields", {})
            confidence = float(parsed.get("confidence", 0.0))
            # 필드 화이트리스트 적용 (신뢰성)
            fields = {k: fields_dict.get(k) for k in _EXTRACT_FIELDS if k in fields_dict}
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            log.warning("ai_intake.parse_failed", error=str(e), raw=raw_text[:200])
            fields = {}
            confidence = 0.0

        log.info("ai_intake.extract.done",
                 filename=filename, fields_count=len(fields), confidence=confidence)
        return {
            "filename": filename,
            "size_bytes": len(file_bytes),
            "fields": fields,
            "confidence": confidence,
        }

    @staticmethod
    def _strip_fences(text: str) -> str:
        """```json ... ``` 마크다운 fence 제거."""
        text = text.strip()
        m = re.match(r"^```(?:json)?\s*\n?([\s\S]*?)\n?```$", text)
        if m:
            return m.group(1).strip()
        return text
