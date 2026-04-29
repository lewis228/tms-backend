# src/ai_intake/providers/base.py
"""IntakeProvider 추상 인터페이스 + 공용 상수.

H-1: containers[] 배열 추출 지원. PDF 1장에 컨테이너 N개 가능.
"""
from __future__ import annotations
import json
import re
from abc import ABC, abstractmethod
from typing import Any, TypedDict


# D/O 헤더 추출 대상 필드 (컨테이너 분리)
EXTRACT_HEADER_FIELDS: list[str] = [
    "bl_number", "booking_number", "reference",
    "customer_name", "vessel_name", "voyage_no",
    "terminal_name", "eta", "direction",
]

# 컨테이너 추출 대상 필드 (containers[] 배열의 각 row)
EXTRACT_CONTAINER_FIELDS: list[str] = [
    "container_number", "size", "type",
    "seal_no", "weight_kg", "chassis_number",
    "pickup_appointment", "delivery_appointment", "return_appointment",
    "demurrage_lfd", "detention_lfd", "empty_date", "loaded_date",
    "delivery_location_name", "return_location_name",
    "service_type",
    "stops",  # v3: Stop 시퀀스 배열
]


SYSTEM_PROMPT = """당신은 운송 D/O (Delivery Order) 문서 OCR 전문 모델입니다.
첨부된 PDF/이미지에서 다음 정보를 추출해 JSON 으로 반환하세요.

D/O 1건은 헤더 정보 + 컨테이너 N개 (1개 이상). 컨테이너 표를 모두 읽어 배열로 반환.

헤더 필드:
- bl_number (B/L 번호, str)
- booking_number (Booking 번호, str)
- reference (Reference, str)
- customer_name (포워딩사/화주 회사명, str)
- vessel_name (선박명, str)
- voyage_no (항차번호, str)
- terminal_name (출발 터미널명, str)
- eta (ISO 8601 datetime, str)
- direction ("IMPORT" 또는 "EXPORT")

컨테이너 필드 (containers 배열의 각 row):
- container_number (^[A-Z]{4}[0-9]{7}$, str)
- size (20GP/40GP/40HC/40OT/45HC/20RF/40RF, str)
- type (DRY/RF/OT 등, str)
- seal_no (str)
- weight_kg (number — kg 단위)
- chassis_number (str)
- pickup_appointment (ISO 8601 datetime, str)
- delivery_appointment (ISO 8601 datetime, str)
- return_appointment (ISO 8601 datetime, str)
- demurrage_lfd (ISO 8601 date, str)
- detention_lfd (ISO 8601 date, str)
- empty_date (ISO 8601 datetime, str)
- loaded_date (ISO 8601 datetime, str)
- delivery_location_name (수하인/창고명, str)
- return_location_name (빈컨 반납지명, str)
- service_type ("LIVE" 또는 "DROP")
- stops (v3): 컨테이너가 거치는 정차 시퀀스 배열. 각 요소:
  - role: "ORIGIN" / "DELIVERY" / "TRANSIT" / "TERMINUS"
  - location_name: 장소명/주소 (str)
  - planned_arrival: ISO 8601 datetime (str, 가능하면)
  - note: 특이사항 (str, optional)

  규칙:
  - 첫 항목은 보통 ORIGIN (터미널/항만/차고 등에서 컨테이너 픽업 지점).
  - 화주 도어/창고는 DELIVERY (LCL이면 N개).
  - 마지막 항목은 보통 TERMINUS (빈 컨 반납 디포 등).
  - 중간 경유점은 TRANSIT.
  - 명시적이지 않으면 stops: [] 빈 배열로 반환.

규칙:
- 명확하지 않은 필드는 null.
- 컨테이너가 1개라도 반드시 배열 형태로 반환 (containers: [{...}]).
- 컨테이너를 못 찾으면 containers: [].
- 추출에 자신 있는 정도를 0.0 ~ 1.0 confidence 로 평가.
- 응답은 반드시 JSON 객체 1개만. 마크다운 fence 없이.
  형식: {"fields": {<header>..., "containers": [{..., "stops": [...]}]}, "confidence": 0.0}
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
        """파일에서 D/O 필드 추출. 실패 시 fields={}, confidence=0."""
        ...


# ─────────────────────────────────────────────────────────────
# 공용 헬퍼
# ─────────────────────────────────────────────────────────────
def strip_fences(text: str) -> str:
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

        # 헤더 화이트리스트 + containers 배열 보존
        fields: dict[str, Any] = {
            k: fields_dict.get(k) for k in EXTRACT_HEADER_FIELDS if k in fields_dict
        }

        raw_containers = fields_dict.get("containers")
        containers_out: list[dict[str, Any]] = []
        if isinstance(raw_containers, list):
            for c in raw_containers:
                if not isinstance(c, dict):
                    continue
                containers_out.append({
                    k: c.get(k) for k in EXTRACT_CONTAINER_FIELDS if k in c
                })
        fields["containers"] = containers_out

        return {"fields": fields, "confidence": confidence}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"fields": {"containers": []}, "confidence": 0.0}


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
