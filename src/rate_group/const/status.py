# src/rate_group/const/status.py
from __future__ import annotations
from enum import StrEnum


class RateMethod(StrEnum):
    ZONE = "ZONE"      # 요율표 필요 (Point × Zone)
    CITY = "CITY"      # 요율표 필요 (Point × City/Zip)
    MILE = "MILE"      # 거리 × 단가
    HOURLY = "HOURLY"  # 시간 × 단가
