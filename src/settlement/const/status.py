# src/settlement/const/status.py
from __future__ import annotations
from enum import StrEnum


class SettlementStatus(StrEnum):
    """Settlement 라이프사이클: PENDING → CALCULATED → ADJUSTED → APPROVED."""
    PENDING    = "PENDING"
    CALCULATED = "CALCULATED"
    ADJUSTED   = "ADJUSTED"
    APPROVED   = "APPROVED"


class SettlementAuditAction(StrEnum):
    """Audit log 의 action 종류."""
    CALCULATE  = "CALCULATE"
    ADJUST     = "ADJUST"
    APPROVE    = "APPROVE"
    UNAPPROVE  = "UNAPPROVE"
