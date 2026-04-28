# src/driver/const/status.py
from __future__ import annotations
from enum import StrEnum


class EmploymentKind(StrEnum):
    """기사 고용 형태."""
    IN_HOUSE             = "IN_HOUSE"             # 사내 (W2)
    OWNER_OPERATOR_SOLO  = "OWNER_OPERATOR_SOLO"  # 프리랜서 단독 (1099, 자기 자신이 1인 carrier)
    CARRIER_DRIVER       = "CARRIER_DRIVER"       # 외부 carrier 소속 (carrier_id 필수)


class PaymentTermsKind(StrEnum):
    """기사 정산 방식."""
    PERCENT_OF_REVENUE = "PERCENT_OF_REVENUE"
    PER_LEG            = "PER_LEG"
    HOURLY             = "HOURLY"
    SALARY             = "SALARY"
