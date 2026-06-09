# src/rate_point/const/status.py
from __future__ import annotations
from enum import StrEnum


class PointType(StrEnum):
    """요율표(Rate Sheet)의 '행'이 되는 Point 종류.

    컨플루언스 [Terry] 요율표 기획: Point = Terminal 또는 Yard.
    고객사(Customer/Zone)는 '열' 이라 여기 포함하지 않는다.
    """
    TERMINAL = "TERMINAL"   # 항만 터미널
    YARD     = "YARD"       # 자사/외부 야드
