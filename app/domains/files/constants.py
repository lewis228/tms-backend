"""File 도메인 상수."""
from __future__ import annotations

# 폴리모픽 첨부 대상 도메인 화이트리스트
ATTACHABLE_DOMAINS: set[str] = {
    "delivery_orders",
    "legs",
    "settlements",
    "drivers",
    "customers",
    "ai_intake",
}

# 파일 종류 (POD = Proof of Delivery, RECEIPT = 영수증, ATTACHMENT = 일반 첨부, INTAKE = AI 추출 원본)
FILE_KINDS: set[str] = {"POD", "RECEIPT", "ATTACHMENT", "INTAKE"}

PRESIGNED_PUT_TTL_SECONDS = 600  # 10 min
PRESIGNED_GET_TTL_SECONDS = 3600  # 1 hour
