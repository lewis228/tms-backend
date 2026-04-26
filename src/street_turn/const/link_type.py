# src/street_turn/const/link_type.py
from __future__ import annotations
from enum import StrEnum


class StreetTurnLinkType(StrEnum):
    """Street turn 연결 방식."""
    AUTO   = "AUTO"    # 시스템이 자동 매칭
    MANUAL = "MANUAL"  # dispatcher 수동 지정
