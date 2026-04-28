# src/truck/const/status.py
from __future__ import annotations
from enum import StrEnum


class TruckOwnerKind(StrEnum):
    """트럭 소유 주체."""
    COMPANY = "COMPANY"   # 우리 회사 자산
    DRIVER  = "DRIVER"    # 외부 기사 / owner-operator 본인 차


class TruckStatus(StrEnum):
    """트럭 가동 상태."""
    ACTIVE      = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    RETIRED     = "RETIRED"
