# src/invoice/const/status.py
from __future__ import annotations
from enum import StrEnum


class InvoiceStatus(StrEnum):
    """고객 인보이스 상태 (재설계 2c)."""
    DRAFT  = "DRAFT"    # 작성 중 — 라인 편집 가능
    ISSUED = "ISSUED"   # 발행됨 — 고객에 청구
    PAID   = "PAID"     # 수금 완료
    VOID   = "VOID"     # 취소/무효


class InvoiceLineSource(StrEnum):
    """청구 라인 출처."""
    PREFILL = "PREFILL"   # D/O 기사 원가에서 시작값 프리필
    MANUAL  = "MANUAL"    # 수동 추가
