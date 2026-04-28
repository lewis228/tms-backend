# src/container/const/status.py
from __future__ import annotations
from enum import StrEnum

from delivery_order.const.status import DeliveryStatus


# Container 자체 상태머신은 D/O 의 DeliveryStatus 를 그대로 재사용한다.
# 디스패처는 컨테이너 단위로도 진행 단계를 수동 변경할 수 있다.
ContainerStatus = DeliveryStatus


class ContainerSize(StrEnum):
    """컨테이너 사이즈."""
    SIZE_20GP = "20GP"
    SIZE_40GP = "40GP"
    SIZE_40HC = "40HC"
    SIZE_40OT = "40OT"
    SIZE_45HC = "45HC"
    SIZE_20RF = "20RF"
    SIZE_40RF = "40RF"


class ContainerEventKind(StrEnum):
    """컨테이너 라이프사이클 이벤트."""
    GATE_OUT      = "GATE_OUT"        # 터미널에서 픽업
    DELIVERED     = "DELIVERED"       # 도착지 도착 / 적재 하역
    EMPTIED       = "EMPTIED"         # 빈 컨테이너 상태로 전환
    STREET_TURNED = "STREET_TURNED"   # export 재사용 시작
    REUSED        = "REUSED"          # street-turn 으로 재사용 leg 시작
    GATE_IN       = "GATE_IN"         # 터미널 게이트 인
    RETURNED      = "RETURNED"        # 빈 컨 반납 완료
