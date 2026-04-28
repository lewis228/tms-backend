# src/leg/const/status.py
from __future__ import annotations
from enum import StrEnum


class LegStatus(StrEnum):
    """Leg 상태 머신: PENDING → IN_TRANSIT → COMPLETED / FAILED / DRY_RUN."""
    PENDING    = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"
    DRY_RUN    = "DRY_RUN"


class MoveType(StrEnum):
    """이동 적재 상태."""
    LOADED = "LOADED"  # 컨테이너 적재 상태
    EMPTY  = "EMPTY"   # 빈 컨테이너
    BOBTAIL = "BOBTAIL"  # 트럭만 (컨X)


class ServiceType(StrEnum):
    """서비스 방식."""
    LIVE = "LIVE"  # 즉시 처리 (기사 대기)
    DROP = "DROP"  # 야드 드롭 후 픽업


class LegKind(StrEnum):
    """leg 동작 분류 (Manifest 의 한 줄 = 1 leg = 1 kind)."""
    BOBTAIL              = "BOBTAIL"               # 트럭만 이동 (컨X)
    PICKUP               = "PICKUP"                # 터미널/야드에서 컨 픽업
    DROP                 = "DROP"                  # 컨을 야드/창고에 떨굼
    LIVE_UNLOAD          = "LIVE_UNLOAD"           # 도착지에서 기사 대기 + 즉시 하역
    RETURN               = "RETURN"                # 빈 컨 반납 (터미널/풀)
    STREET_TURN          = "STREET_TURN"           # 빈 컨 재사용 (다른 export)
    CHASSIS_FLIP         = "CHASSIS_FLIP"          # 한 stop 에서 컨 swap
    DRY_RUN              = "DRY_RUN"               # 빠꾸 (현장 도착했으나 작업 불가)
    REPOSITION           = "REPOSITION"            # 빈 컨/챠시 재배치
    PARTIAL_PICKUP       = "PARTIAL_PICKUP"        # 분할 픽업 (한 BL 의 컨 일부만)
    MULTI_STOP_DELIVERY  = "MULTI_STOP_DELIVERY"   # 여러 곳에 분할 배송


class StopKind(StrEnum):
    """leg_stop 의 stop 종류."""
    PICKUP_FULL      = "PICKUP_FULL"       # 적재 컨 픽업
    DROP_FULL        = "DROP_FULL"         # 적재 컨 떨굼
    PICKUP_EMPTY     = "PICKUP_EMPTY"      # 빈 컨 픽업
    DROP_EMPTY       = "DROP_EMPTY"        # 빈 컨 떨굼 (반납 등)
    CHASSIS_GET      = "CHASSIS_GET"       # 챠시 빌림 (풀에서)
    CHASSIS_RETURN   = "CHASSIS_RETURN"    # 챠시 반납
    WAIT             = "WAIT"              # 대기
    FUEL             = "FUEL"              # 주유
    SCALE            = "SCALE"             # 계량
    OTHER            = "OTHER"


class ChassisEventKind(StrEnum):
    """챠시 라이프사이클 이벤트."""
    PICKED_UP             = "PICKED_UP"              # 챠시 픽업
    DROPPED_OFF           = "DROPPED_OFF"            # 챠시 떨굼
    FLIPPED               = "FLIPPED"                # 챠시-컨 swap
    RETURNED_TO_POOL      = "RETURNED_TO_POOL"       # 풀에 반납
    RETURNED_TO_TERMINAL  = "RETURNED_TO_TERMINAL"   # 터미널에 반납
