# src/leg_layer/const/status.py
from __future__ import annotations
from enum import StrEnum


class LegAddonCode(StrEnum):
    """Leg Add-on 코드 (추가요금 한 줄, 중복 가능).

    컨플루언스 재정의(2026-06-10): Layer 1/2/3 구분 폐기. 옛 Add-on(Layer2) + 옛 Charge Event(Layer3:
    DET/DMR/YRD/STP) 를 모두 add-on 코드로 통합. Stop Off(STP) 도 add-on 으로 ×N 부착.
    """
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
    # 옛 Charge Event(Layer3 폐기) → add-on 으로 흡수
    STP = "STP"   # Stop Off / Stop Over (경유지마다 1개)
    DET = "DET"   # Detention (Waiting) — (실체류−Free)×시간당, amount 저장
    DMR = "DMR"   # Demurrage — 일당
    YRD = "YRD"   # Yard Storage — 일당
