# src/equipment_pool/const/status.py
from __future__ import annotations
from enum import StrEnum


class EquipmentPoolKind(StrEnum):
    """챠시 풀 종류."""
    TERMINAL_POOL    = "TERMINAL_POOL"     # 터미널이 운영하는 풀 (예: GCT-NJ chassis pool)
    THIRD_PARTY_POOL = "THIRD_PARTY_POOL"  # TRAC / FlexiVan / DCLI 등 별도 사업자 풀
