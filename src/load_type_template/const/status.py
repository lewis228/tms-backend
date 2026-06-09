# src/load_type_template/const/status.py
from __future__ import annotations
from enum import StrEnum


class LoadDirection(StrEnum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    BOTH   = "BOTH"


class TemplateLocationType(StrEnum):
    """Leg From/To 의 Location 종류 (재설계 표준)."""
    TERMINAL = "TERMINAL"
    YARD     = "YARD"
    CUSTOMER = "CUSTOMER"


class TemplateMoveType(StrEnum):
    """이동 구간 적재상태."""
    LOAD  = "LOAD"
    EMPTY = "EMPTY"
    NONE  = "NONE"   # Bobtail


class TemplateServiceType(StrEnum):
    """도착지 처리 방식."""
    LIVE = "LIVE"
    DROP = "DROP"
    NONE = "NONE"


class TemplateMoveCode(StrEnum):
    """Layer1 Move Type 코드 (요율 계산 기준, 컨플루언스 Leg 유형 분석)."""
    PPU = "PPU"   # Port Pick-up
    PRE = "PRE"   # Port Return
    PPL = "PPL"   # Pre-pull
    DRP = "DRP"   # Drop & Pick
    STR = "STR"   # Street Turn
    TRL = "TRL"   # Transload
    RMP = "RMP"   # Rail Ramp
    OTR = "OTR"   # Over-the-Road
    ERP = "ERP"   # Empty Reposition
