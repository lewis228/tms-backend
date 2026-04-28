# src/charge_code/const/status.py
from __future__ import annotations
from enum import StrEnum


class ChargeKind(StrEnum):
    """청구 코드 분류."""
    BASE        = "BASE"          # 기본 운임
    ACCESSORIAL = "ACCESSORIAL"   # 부가 (Wait / Chassis Split / Bobtail / Dry Run 등)
    PENALTY     = "PENALTY"       # Demurrage / Detention 등 페널티
    FUEL        = "FUEL"          # 연료 surcharge
    TAX         = "TAX"           # VAT / GST 등 세금
    DISCOUNT    = "DISCOUNT"      # 할인


class ChargeUnit(StrEnum):
    """청구 단위."""
    FLAT    = "FLAT"     # 정액
    HOUR    = "HOUR"     # 시간당
    MINUTE  = "MINUTE"   # 분당
    DAY     = "DAY"      # 일당 (per-diem)
    MILE    = "MILE"     # 마일당
    PERCENT = "PERCENT"  # %


class ChargeSource(StrEnum):
    """leg_charge 가 어떻게 생성되었는지."""
    AUTO   = "AUTO"     # rate_card 매칭으로 자동 생성
    MANUAL = "MANUAL"   # 운영자 수동 추가
    EVENT  = "EVENT"    # 이벤트 (예: chassis_event 시간차 → CHASSIS_PER_DIEM)


class PartyKind(StrEnum):
    """leg_charge 의 payee_kind / payer_kind 다형성.

    - CUSTOMER: customer 테이블 (kind=CUSTOMER 등)
    - CARRIER: customer 테이블 (kind=CARRIER) — 외주 협력사
    - DRIVER: driver 테이블
    - COMPANY: 우리 회사 자체 (P&L 의 자기 계정)
    - POOL: equipment_pool (챠시 풀 사용료)
    """
    CUSTOMER = "CUSTOMER"
    CARRIER  = "CARRIER"
    DRIVER   = "DRIVER"
    COMPANY  = "COMPANY"
    POOL     = "POOL"
