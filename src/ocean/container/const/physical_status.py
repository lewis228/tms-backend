"""컨테이너 물리적 진행 상태 Enum.

Shipment 수준의 "트래킹 작업 상태" (pending / tracking / failed / ...) 와
구분된다. 이쪽은 **컨테이너가 지금 어디쯤 있나** 를 답하는 축이며 프론트
Shipments 리스트의 탭 분류(On Ship / Arrived / Stopped Tracking) 에 사용된다.

Raw 이벤트 description (예: "Empty returned", "Gate out - Empty", "Discharged")
을 `normalizer.normalize_physical_status` 가 이 Enum 값 중 하나로 해석해서
`ocean_containers.physical_status` 에 저장한다. Raw 는 `.status` 컬럼에 보존.

상태 순서(일반적 여정):
    REGISTERED → GATE_IN → LOADED → ON_SHIP → DISCHARGED → GATE_OUT → EMPTY_RETURNED

매 상태는 독립적이며, 스크래퍼가 일부를 건너뛸 수 있다. `UNKNOWN` 은
정규식 매칭 실패 fallback — 로그 모니터링으로 새 패턴을 포착해 규칙에 추가.
"""

from enum import StrEnum


class ContainerPhysicalStatus(StrEnum):
    REGISTERED = "registered"          # MBL 등록만, 아직 이벤트 없음
    GATE_IN = "gate_in"                # 출발 터미널 진입 (빈 컨테이너 출고 포함)
    LOADED = "loaded"                  # 배에 적재 완료, 미출항
    ON_SHIP = "on_ship"                # 운송 중 (Vessel departed ~ Vessel arrived)
    DISCHARGED = "discharged"          # POD 에서 하선 완료
    GATE_OUT = "gate_out"              # 터미널 픽업 / 반출 (수하인 인수)
    EMPTY_RETURNED = "empty_returned"  # 빈 컨테이너 반납 완료 (여정 종료)
    UNKNOWN = "unknown"                # 매칭 실패 fallback
