# src/service_area/const/status.py
from __future__ import annotations
from enum import StrEnum


class ServiceAreaKind(StrEnum):
    """영업권역 선언 단위 (설계문서 §8 방어 1) — 넓은 것부터 좁은 것."""
    STATE = "STATE"    # 주 전체 (value = state 와 동일값)
    COUNTY = "COUNTY"  # 카운티 (value = 카운티명)
    CITY = "CITY"      # 도시 (value = 도시명)
    ZIP3 = "ZIP3"      # 3자리 ZIP prefix — USPS 섹셔널 센터 (value = "902" 등)
