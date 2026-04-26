# src/leg/const/status.py
from __future__ import annotations
from enum import StrEnum


class LegStatus(StrEnum):
    """Leg 상태 머신: PENDING → IN_TRANSIT → COMPLETED / FAILED"""
    PENDING    = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"


class MoveType(StrEnum):
    """이동 적재 상태."""
    LOADED = "LOADED"  # 컨테이너 적재 상태
    EMPTY  = "EMPTY"   # 빈 컨테이너


class ServiceType(StrEnum):
    """서비스 방식."""
    LIVE = "LIVE"  # 즉시 처리 (기사 대기)
    DROP = "DROP"  # 야드 드롭 후 픽업
