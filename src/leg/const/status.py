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


class LegLocationType(StrEnum):
    """재설계: Leg From/To 의 Location 종류 (컨플루언스 Leg 유형 분석)."""
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


class StopRole(StrEnum):
    """v3 컨테이너 정차점(Stop)의 역할 — 4가지로 단순화.

    - ORIGIN     : 첫 시작점 (보통 터미널, 항만, 차고 등 — 필수 X).
    - DELIVERY   : 화주 도어/창고 등 화물을 내리거나 적재하는 지점. N개 가능 (LCL).
    - TRANSIT    : 중간 경유 (휴식·환승). 적재 변화 없음.
    - TERMINUS   : 마지막 종료점 (보통 빈 컨 반납 디포 — 필수 X).

    액션(픽업/드롭/empty/full)은 이 role + 인접 leg.move_type 조합으로 derive.
    시간 소비형(WAIT/FUEL/SCALE) 은 stop 이 아니라 leg_layer/정산 라인으로 흡수.
    """
    ORIGIN   = "ORIGIN"
    DELIVERY = "DELIVERY"
    TRANSIT  = "TRANSIT"
    TERMINUS = "TERMINUS"


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


class MoveTypeV3(StrEnum):
    """v3 Leg.move_type 4축 형상.

    - TRUCK_ONLY    : 트럭만. 차고→터미널 등.
    - CHASSIS_ONLY  : 트럭+섀시만. 섀시 픽업/반납/이동.
    - EMPTY_LOADED  : 빈 컨 적재 상태 이동.
    - FULL_LOADED   : 적재 컨 이동.

    기존 MoveType 매핑: LOADED→FULL_LOADED, EMPTY→EMPTY_LOADED, BOBTAIL→TRUCK_ONLY.
    """
    TRUCK_ONLY    = "TRUCK_ONLY"
    CHASSIS_ONLY  = "CHASSIS_ONLY"
    EMPTY_LOADED  = "EMPTY_LOADED"
    FULL_LOADED   = "FULL_LOADED"


class ChassisEventKind(StrEnum):
    """챠시 라이프사이클 이벤트."""
    PICKED_UP             = "PICKED_UP"              # 챠시 픽업
    DROPPED_OFF           = "DROPPED_OFF"            # 챠시 떨굼
    FLIPPED               = "FLIPPED"                # 챠시-컨 swap
    RETURNED_TO_POOL      = "RETURNED_TO_POOL"       # 풀에 반납
    RETURNED_TO_TERMINAL  = "RETURNED_TO_TERMINAL"   # 터미널에 반납
