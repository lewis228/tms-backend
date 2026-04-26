# src/location/const/kind.py
from __future__ import annotations
from enum import StrEnum


class LocationKind(StrEnum):
    """장소 종류."""
    YARD = "YARD"          # 야드 (컨테이너 임시 보관)
    CUSTOMER = "CUSTOMER"  # 고객사 주소
    PORT = "PORT"          # 항만
    OTHER = "OTHER"
