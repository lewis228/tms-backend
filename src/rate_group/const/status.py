# src/rate_group/const/status.py
from __future__ import annotations
from enum import StrEnum


class RateMethod(StrEnum):
    """정산 방식 4가지. 존(zone)은 방식이 아니라 ZIP/CITY 원자를 묶는 압축 레이어."""
    ZIP = "ZIP"        # zip ↔ zip 구간 매트릭스 (원자=zip, 존으로 묶기 가능)
    CITY = "CITY"      # 도시 ↔ 도시 구간 매트릭스 (원자=도시, 도시존으로 묶기 가능)
    MILE = "MILE"      # 거리 × 단가
    HOURLY = "HOURLY"  # 시간 × 단가
