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
    DISPATCHING    = "DISPATCHING"   # 재설계: 일부 leg 배차됨(미배차 leg 존재) — 자동 파생
    DISPATCHED     = "DISPATCHED"
    YARD_STAGED    = "YARD_STAGED"
    FINAL_DELIVERY = "FINAL_DELIVERY"
    EMPTY_STAGED   = "EMPTY_STAGED"
    COMPLETED      = "COMPLETED"


class ShipmentDirection(StrEnum):
    """수입/수출 방향."""
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
