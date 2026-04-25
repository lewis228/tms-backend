"""컨테이너 이벤트 타입 Enum.

선사 사이트의 raw event description 을 정규화한 분류. 타임라인 UI 에서
아이콘 / 색상 매핑에 사용하고 "얼마나 많은 Gate out 이 지난 30일 발생?" 같은
집계 쿼리의 그룹키로도 사용된다.

Raw 는 `ocean_container_events.event_type` (이미 존재) 에 보존,
정규화 값은 `ocean_container_events.event_type_code` 에 저장.
"""

from enum import StrEnum


class ContainerEventType(StrEnum):
    GATE_IN = "gate_in"                  # 출발 터미널 진입
    LOADED = "loaded"                    # 배에 적재
    VESSEL_DEPARTED = "vessel_departed"  # 배 출항
    VESSEL_ARRIVED = "vessel_arrived"    # 배 입항 (POD 기항)
    DISCHARGED = "discharged"            # 하선 완료
    GATE_OUT = "gate_out"                # 터미널 픽업 / 반출
    EMPTY_RETURNED = "empty_returned"    # 빈 컨테이너 반납
    RAIL_DEPARTED = "rail_departed"      # 철도 출발 (inland)
    RAIL_ARRIVED = "rail_arrived"        # 철도 도착
    TRANSSHIPMENT = "transshipment"      # T/S 환적
    UNKNOWN = "unknown"                  # 매칭 실패 fallback
