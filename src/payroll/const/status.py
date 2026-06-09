# src/payroll/const/status.py
from __future__ import annotations
from enum import StrEnum


class PayrollStatus(StrEnum):
    """드라이버 정산(payroll) 상태."""
    DRAFT     = "DRAFT"      # 계산됨, 수정 가능
    CONFIRMED = "CONFIRMED"  # 확정(라인 동결)
    PAID      = "PAID"       # 지급 완료
    VOID      = "VOID"       # 취소


class PayrollLineSource(StrEnum):
    """정산 라인 base 의 출처."""
    RESOLVED   = "RESOLVED"    # RateResolver 로 산출
    UNRESOLVED = "UNRESOLVED"  # 요율 미등록/그룹 미배정 등 → 경고, 확정 차단
    MANUAL     = "MANUAL"      # 수동 입력
