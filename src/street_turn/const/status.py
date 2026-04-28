# src/street_turn/const/status.py
from __future__ import annotations
from enum import StrEnum


class StreetTurnStatus(StrEnum):
    """Street Turn 승인 워크플로우 상태."""
    REQUESTED = "REQUESTED"  # 요청됨 (선사 승인 대기)
    APPROVED  = "APPROVED"   # 승인 완료
    REJECTED  = "REJECTED"   # 거절
    CANCELLED = "CANCELLED"  # 디스패처 자체 취소
