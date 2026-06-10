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


class ChargeCategory(StrEnum):
    """변동 청구 라인 분류 (UI 그룹핑·필터·signed 기본값 결정).

    - BASE        : 기본 운임은 요율표가 다루지만, 수동 라인이면 여기.
    - WAITING     : 대기 수당 (분당/정액).
    - EXTRA_STOP  : 추가 정차/섀시 대여 지체 등.
    - DRY_RUN     : 빠꾸/터미널 closed 헛걸음 보상.
    - PENALTY     : 기사 과실 등 음수.
    - SURCHARGE   : 유류·심야 할증 등.
    - ADJUSTMENT  : segment 분배 / base_portion_split 등 양·음 redistribute.
    - OTHER       : 분류 외.
    """
    BASE       = "BASE"
    WAITING    = "WAITING"
    EXTRA_STOP = "EXTRA_STOP"
    DRY_RUN    = "DRY_RUN"
    PENALTY    = "PENALTY"
    SURCHARGE  = "SURCHARGE"
    ADJUSTMENT = "ADJUSTMENT"
    OTHER      = "OTHER"


class ChargeUnit(StrEnum):
    """청구 단위."""
    FLAT    = "FLAT"     # 정액
    HOUR    = "HOUR"     # 시간당
    MINUTE  = "MINUTE"   # 분당
    DAY     = "DAY"      # 일당 (per-diem)
    MILE    = "MILE"     # 마일당
    PERCENT = "PERCENT"  # %


class ChargeSource(StrEnum):
    """청구 라인이 어떻게 생성되었는지."""
    AUTO   = "AUTO"     # 요율/규칙 매칭으로 자동 생성
    MANUAL = "MANUAL"   # 운영자 수동 추가
    EVENT  = "EVENT"    # 이벤트 (예: chassis_event 시간차 → CHASSIS_PER_DIEM)


class PartyKind(StrEnum):
    """청구 라인의 payee_kind / payer_kind 다형성.

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
