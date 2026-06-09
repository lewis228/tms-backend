# src/leg_layer/const/status.py
from __future__ import annotations
from enum import StrEnum


class LegAddonCode(StrEnum):
    """Layer 2 — Add-on (복수 선택). 컨플루언스 Leg 유형 분석."""
    CHS = "CHS"   # Chassis Split
    HZM = "HZM"   # Hazmat
    OOG = "OOG"   # OOG / Oversize
    RFR = "RFR"   # Reefer Monitor
    CXM = "CXM"   # Customs Exam
    LYO = "LYO"   # Layover
    RSP = "RSP"   # Respot
    FLT = "FLT"   # Flat Rack
    TNK = "TNK"   # Tanker
    NGT = "NGT"   # Night Gate
    WKD = "WKD"   # Weekend
    EGT = "EGT"   # Early Gate
    LFT = "LFT"   # Lift
    PPS = "PPS"   # Pier Pass


class LegChargeEventCode(StrEnum):
    """Layer 3 — Charge Event (토글 + Free Time 초과분 자동 계산)."""
    DET = "DET"   # Detention (Waiting) — 시간당
    DMR = "DMR"   # Demurrage — 일당
    YRD = "YRD"   # Yard Storage — 일당
    STP = "STP"   # Stop Over
