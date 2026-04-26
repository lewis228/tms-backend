# src/rate_setting/const/rate_type.py
from __future__ import annotations
from enum import StrEnum


class RateType(StrEnum):
    """요율 종류."""
    FLAT_RATE = "FLAT_RATE"        # 정액
    PERCENTAGE = "PERCENTAGE"      # 비율
    PER_MILE = "PER_MILE"          # 마일 당
