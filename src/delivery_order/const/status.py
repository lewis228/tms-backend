# src/delivery_order/const/status.py
from __future__ import annotations
from enum import StrEnum


class DeliveryStatus(StrEnum):
    """D/O 상태 머신.

    PLANNING → DISPATCHED ─┬─► YARD_STAGED ─► FINAL_DELIVERY ─┬─► EMPTY_STAGED ─► COMPLETED
                           │                                  │
                           └──► FINAL_DELIVERY ───────────────┴─► COMPLETED
    """
    PLANNING       = "PLANNING"
    DISPATCHED     = "DISPATCHED"
    YARD_STAGED    = "YARD_STAGED"
    FINAL_DELIVERY = "FINAL_DELIVERY"
    EMPTY_STAGED   = "EMPTY_STAGED"
    COMPLETED      = "COMPLETED"


class ShipmentDirection(StrEnum):
    """수입/수출 방향."""
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"


class ContainerSize(StrEnum):
    """컨테이너 사이즈."""
    SIZE_20GP = "20GP"
    SIZE_40GP = "40GP"
    SIZE_40HC = "40HC"
    SIZE_40OT = "40OT"
    SIZE_45HC = "45HC"
    SIZE_20RF = "20RF"
    SIZE_40RF = "40RF"
