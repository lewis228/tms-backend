# src/accessorial/const/status.py
from __future__ import annotations
from enum import StrEnum


class AccessorialCategory(StrEnum):
    """부가요금/Surcharge 분류 (컨플루언스 Add-on / Charge Event / Flag 통합)."""
    WAITING      = "WAITING"        # Detention(대기)
    EXTRA_STOP   = "EXTRA_STOP"     # Stop Off
    DRY_RUN      = "DRY_RUN"        # 헛걸음
    PENALTY      = "PENALTY"        # Demurrage/Detention 페널티
    SURCHARGE    = "SURCHARGE"      # 일반 할증
    FUEL         = "FUEL"           # 연료 할증(드라이버별)
    CHASSIS_SPLIT = "CHASSIS_SPLIT"  # 챠시 스플릿
    PREPULL      = "PREPULL"        # Pre-pull
    LIFT         = "LIFT"           # 리프트
    NIGHT_GATE   = "NIGHT_GATE"     # 야간 게이트
    PIER_PASS    = "PIER_PASS"      # Pier Pass
    HAZMAT       = "HAZMAT"
    REEFER       = "REEFER"
    OVERWEIGHT   = "OVERWEIGHT"
    STORAGE      = "STORAGE"        # Yard Storage
    ADJUSTMENT   = "ADJUSTMENT"     # 수동 보정
    OTHER        = "OTHER"


class AccessorialUnit(StrEnum):
    """과금 단위."""
    FLAT    = "FLAT"     # 정액
    HOUR    = "HOUR"     # 시간당
    MINUTE  = "MINUTE"   # 분당
    DAY     = "DAY"      # 일당 (per-diem)
    MILE    = "MILE"     # 마일당
    PERCENT = "PERCENT"  # % (FUEL 등)
