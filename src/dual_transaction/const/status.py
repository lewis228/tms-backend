# src/dual_transaction/const/status.py
from __future__ import annotations
from enum import StrEnum


class DualTransactionStatus(StrEnum):
    """Dual Transaction(반납+픽업 1드라이버 묶음) 상태."""
    PLANNED   = "PLANNED"     # 묶음 계획됨
    COMPLETED = "COMPLETED"   # 두 leg 모두 완료
    CANCELLED = "CANCELLED"   # 취소
