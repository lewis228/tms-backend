"""AI Intake — Anthropic Claude API 로 PDF/이미지 OCR + 필드 추출.

전제: settings.anthropic_api_key 설정. 빈 값이면 503 (도메인 비활성).
파일 source: file_id (files 도메인 다운로드) 또는 base64_data 직접.
"""
from __future__ import annotations

import base64
import json
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings
from app.core.exceptions import NotFoundError, TMSException, ValidationError
from app.core.storage import get_s3
from app.domains.ai_intake.schema import (
    IntakeExtractRequest,
    IntakeExtractResponse,
    IntakeField,
)
from app.domains.files.repository import FileRepository

DEFAULT_MODEL = "claude-sonnet-4-6"

_PROMPT = """\
You are an expert at extracting drayage delivery order data from shipping documents.
Given the attached PDF/image of a shipping document (Delivery Order, B/L, booking confirmation),
extract the following fields. For each field, return both `value` (string or null) and `confidence`
(0.0 to 1.0). Use null when the field is missing or unreadable.

Return STRICT JSON in the schema below — no markdown fences, no commentary.

{
  "direction": "IMPORT" | "EXPORT" | null,
  "bl_number": {"value": str|null, "confidence": float},
  "booking_number": {"value": str|null, "confidence": float},
  "container_number": {"value": str|null, "confidence": float},
  "container_size": "20GP" | "40GP" | "40HC" | "40OT" | "45HC" | "20RF" | "40RF" | null,
  "chassis_number": {"value": str|null, "confidence": float},
  "customer_name": {"value": str|null, "confidence": float},
  "terminal_name": {"value": str|null, "confidence": float},
  "vessel_name": {"value": str|null, "confidence": float},
  "eta": "YYYY-MM-DDTHH:MM:SSZ" | null,
  "pickup_appointment": "YYYY-MM-DDTHH:MM:SSZ" | null,
  "delivery_appointment": "YYYY-MM-DDTHH:MM:SSZ" | null,
  "demurrage_lfd": "YYYY-MM-DD" | null,
  "overall_confidence": float,
  "raw_text": str | null
}

Rules:
- container_number must match ^[A-Z]{4}\\d{7}$, otherwise null with confidence 0.
- Dates/times in document timezone — convert to UTC ISO 8601 if timezone is clear, else keep document time with Z suffix.
- overall_confidence reflects how sure you are about the document being a recognizable D/O.
"""


class AIIntakeService:
    def __init__(self, file_repo: FileRepository | None = None) -> None:
        if not settings.anthropic_api_key:
            raise TMSException(
                "AI Intake disabled: ANTHROPIC_API_KEY not set",
                code="ERR_AI_DISABLED",
                status_code=503,
            )
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.file_repo = file_repo

    async def extract(
        self, payload: IntakeExtractRequest, *, model: str = DEFAULT_MODEL
    ) -> IntakeExtractResponse:
        b64, media_type = await self._resolve_source(payload)
        msg = await self.client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document"
                            if media_type == "application/pdf"
                            else "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )
        text_blocks = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        if not text_blocks:
            raise TMSException("Empty AI response", code="ERR_AI_EMPTY")
        try:
            data = json.loads(text_blocks[0])
        except json.JSONDecodeError as e:
            raise TMSException(
                "AI returned non-JSON",
                code="ERR_AI_PARSE",
                details={"raw": text_blocks[0][:500]},
            ) from e
        return self._to_response(data, model=model)

    async def _resolve_source(
        self, payload: IntakeExtractRequest
    ) -> tuple[str, str]:
        if payload.base64_data:
            return payload.base64_data, payload.media_type
        if payload.file_id and self.file_repo is not None:
            f = await self.file_repo.get_by_id(payload.file_id)
            if not f:
                raise NotFoundError("File not found")
            obj = get_s3().get_object(
                Bucket=settings.minio_bucket, Key=f.storage_key
            )
            data: bytes = obj["Body"].read()
            return base64.b64encode(data).decode("ascii"), f.content_type
        raise ValidationError("file_id or base64_data required")

    def _to_response(
        self, data: dict[str, Any], *, model: str
    ) -> IntakeExtractResponse:
        def _f(k: str) -> IntakeField | None:
            v = data.get(k)
            if v is None:
                return None
            if isinstance(v, dict):
                return IntakeField(value=v.get("value"), confidence=float(v.get("confidence", 0)))
            return IntakeField(value=str(v), confidence=0.5)

        return IntakeExtractResponse(
            direction=data.get("direction"),
            bl_number=_f("bl_number"),
            booking_number=_f("booking_number"),
            container_number=_f("container_number"),
            container_size=data.get("container_size"),
            chassis_number=_f("chassis_number"),
            customer_name=_f("customer_name"),
            terminal_name=_f("terminal_name"),
            vessel_name=_f("vessel_name"),
            eta=data.get("eta"),
            pickup_appointment=data.get("pickup_appointment"),
            delivery_appointment=data.get("delivery_appointment"),
            demurrage_lfd=data.get("demurrage_lfd"),
            overall_confidence=float(data.get("overall_confidence", 0.0)),
            raw_text=data.get("raw_text"),
            model=model,
        )
