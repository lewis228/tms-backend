# src/chassis/const/status.py
from __future__ import annotations
from enum import StrEnum


class ChassisOwnerKind(StrEnum):
    """챠시 소유 주체."""
    COMPANY          = "COMPANY"           # 회사 자산
    DRIVER           = "DRIVER"            # 외부기사 본인
    TERMINAL_POOL    = "TERMINAL_POOL"     # 터미널 풀
    THIRD_PARTY_POOL = "THIRD_PARTY_POOL"  # TRAC / FlexiVan 등


class ChassisSize(StrEnum):
    """챠시 사이즈."""
    SIZE_20 = "20"
    SIZE_40 = "40"
    SIZE_45 = "45"
    COMBO   = "COMBO"  # 20+20 combo chassis


class ChassisStatus(StrEnum):
    """챠시 가동 상태."""
    AVAILABLE   = "AVAILABLE"
    IN_USE      = "IN_USE"
    AT_POOL     = "AT_POOL"
    MAINTENANCE = "MAINTENANCE"
