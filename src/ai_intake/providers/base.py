# src/ai_intake/providers/base.py
"""IntakeProvider 추상 인터페이스 + 공용 상수."""
from __future__ import annotations
import json
import re
from abc import ABC, abstractmethod
from typing import Any, TypedDict


# 추출 대상 필드 — D/O 의 주요 컬럼.
EXTRACT_FIELDS: list[str] = [
    "bl_number", "booking_number", "reference",
    "container_number", "container_size", "container_type",
    "chassis_number",
    "eta", "pickup_appointment", "delivery_appointment", "return_appointment",
    "demurrage_lfd", "detention_lfd",
]


SYSTEM_PROMPT = """당신은 운송 D/O (Delivery Order) 문서 OCR 전문 모델입니다.
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


class ExtractResult(TypedDict):
    fields: dict[str, Any]
    confidence: float


class IntakeProvider(ABC):
    """모든 AI provider 가 구현해야 하는 공통 인터페이스."""

    name: str = "abstract"

    @abstractmethod
    async def extract(
        self,
        *,
        file_bytes: bytes,
        content_type: str,
        filename: str,
    ) -> ExtractResult:
        """파일에서 D/O 필드 추출.

        실패 시 RuntimeError. 파싱 실패 시 fields={}, confidence=0 반환.
        """
        ...


# ─────────────────────────────────────────────────────────────
# 공용 헬퍼
# ─────────────────────────────────────────────────────────────
def strip_fences(text: str) -> str:
    """```json ... ``` 마크다운 fence 제거."""
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*\n?([\s\S]*?)\n?```$", text)
    if m:
        return m.group(1).strip()
    return text


def parse_response(raw_text: str) -> ExtractResult:
    """provider 응답 텍스트 → {fields, confidence}. 실패 시 빈 결과."""
    try:
        parsed = json.loads(strip_fences(raw_text))
        fields_dict = parsed.get("fields", {}) or {}
        confidence = float(parsed.get("confidence", 0.0) or 0.0)
        # 화이트리스트 적용
        fields = {k: fields_dict.get(k) for k in EXTRACT_FIELDS if k in fields_dict}
        return {"fields": fields, "confidence": confidence}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"fields": {}, "confidence": 0.0}


def media_type(content_type: str) -> str:
    """Claude / Gemini 가 받아들이는 형태로 정규화."""
    ct = (content_type or "").lower()
    if ct in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        return ct
    if ct == "image/heic":
        return "image/jpeg"
    if ct == "application/pdf":
        return "application/pdf"
    return "image/jpeg"
