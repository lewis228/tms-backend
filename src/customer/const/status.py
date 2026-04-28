# src/customer/const/status.py
from __future__ import annotations
from enum import StrEnum


class PartnerKind(StrEnum):
    """customer 테이블의 역할 분류 (partner 통합).

    - CUSTOMER: 우리에게 운송을 의뢰 (D/O 발급) — 매출
    - CARRIER : 외부 운송사 (외주 협력) — 매입
    - BROKER  : 중개사
    - VENDOR  : 챠시풀/연료/정비 등 일반 공급사
    """
    CUSTOMER = "CUSTOMER"
    CARRIER  = "CARRIER"
    BROKER   = "BROKER"
    VENDOR   = "VENDOR"
