# src/leg/const/status.py
from __future__ import annotations
from enum import StrEnum


class LegStatus(StrEnum):
    """Leg 상태 머신 (컨플루언스 재설계):
    PENDING → ASSIGNED → IN_TRANSIT → COMPLETED / FAILED.
    (ASSIGNED = 드라이버 배차 완료, 운행 시작 전. DRY_RUN 은 레거시 호환 유지.)
    """
    PENDING    = "PENDING"
    ASSIGNED   = "ASSIGNED"     # 재설계: 드라이버 배차 완료, 운행 전
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"
    DRY_RUN    = "DRY_RUN"      # 레거시 호환


class MoveType(StrEnum):
    """이동 적재 상태."""
    LOADED = "LOADED"  # 컨테이너 적재 상태
    EMPTY  = "EMPTY"   # 빈 컨테이너
    BOBTAIL = "BOBTAIL"  # 트럭만 (컨X)


class ServiceType(StrEnum):
    """서비스 방식 (도착지 처리)."""
    LIVE = "LIVE"  # 즉시 처리 (기사 대기)
    DROP = "DROP"  # 야드 드롭 후 픽업
    NONE = "NONE"  # 재설계: Bobtail/Shunt/Failed (처리 없음)


class PointType(StrEnum):
    """Point(=container_stop) / Leg From·To 의 종류. 타입별로 다른 마스터를 가리킨다:
    TERMINAL→terminal, YARD→location(kind=YARD), CUSTOMER→customer.
    (구 LegLocationType 와 동일 값 — 포인트 모델로 통일.)
    """
    TERMINAL = "TERMINAL"
    YARD     = "YARD"
    CUSTOMER = "CUSTOMER"


class LegMoveCode(StrEnum):
    """재설계: Layer1 Move Type 코드 (요율 계산 기준)."""
    PPU = "PPU"   # Port Pick-up
    PRE = "PRE"   # Port Return
    PPL = "PPL"   # Pre-pull
    DRP = "DRP"   # Drop & Pick
    STR = "STR"   # Street Turn
    TRL = "TRL"   # Transload
    RMP = "RMP"   # Rail Ramp
    OTR = "OTR"   # Over-the-Road
    ERP = "ERP"   # Empty Reposition


class HandoverReason(StrEnum):
    """v3 LegDriverSegment 의 기사 인계 사유."""
    TERMINAL_CLOSED = "TERMINAL_CLOSED"
    ACCIDENT        = "ACCIDENT"
    SHIFT_CHANGE    = "SHIFT_CHANGE"
    OTHER           = "OTHER"


class ContainerState(StrEnum):
    """v3 Container 작업 단위 상태 8단계 (자동 derive — HOLD/CANCELLED 만 수동).

    DRAFT          : Stop 0 개. 디스패처 아직 손 안 댐.
    PLANNED        : Stop 1+, 모든 leg PENDING. 출발 전.
    IN_TRANSIT     : 활성 leg = IN_TRANSIT. 도로 위.
    AT_STOP        : 어떤 Stop 도착, 다음 leg 는 있고 PENDING.
    WAITING_PLAN   : 마지막 plan 된 Stop 도착, 다음 Stop/leg 미생성. ⚠️
    HOLD           : 사고/사유로 보류 (수동 토글).
    COMPLETED      : 마지막 TERMINUS 도착 + 모든 leg COMPLETED. 종착.
    CANCELLED      : 의뢰 취소 (수동 토글).
    """
    DRAFT        = "DRAFT"
    PLANNED      = "PLANNED"
    IN_TRANSIT   = "IN_TRANSIT"
    AT_STOP      = "AT_STOP"
    WAITING_PLAN = "WAITING_PLAN"
    HOLD         = "HOLD"
    COMPLETED    = "COMPLETED"
    CANCELLED    = "CANCELLED"


class ChassisEventKind(StrEnum):
    """챠시 라이프사이클 이벤트."""
    PICKED_UP             = "PICKED_UP"              # 챠시 픽업
    DROPPED_OFF           = "DROPPED_OFF"            # 챠시 떨굼
    FLIPPED               = "FLIPPED"                # 챠시-컨 swap
    RETURNED_TO_POOL      = "RETURNED_TO_POOL"       # 풀에 반납
    RETURNED_TO_TERMINAL  = "RETURNED_TO_TERMINAL"   # 터미널에 반납
