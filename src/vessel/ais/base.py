"""AIS provider 인터페이스.

================================================================================
왜 추상화?
================================================================================
현재 지원 후보:
  - MarineTraffic (`services.marinetraffic.com`) — 가장 범용
  - VesselFinder (`api.vesselfinder.com`) — 값 저렴, 미국 커버리지 강함
  - Spire Maritime (`api.spire.com`) — 위성 AIS 강점, GraphQL
  - Mock (개발 / 테스트 전용)

어느 쪽을 선택해도 도메인 코드 (service / task) 는 **그대로** 작동해야 한다.
따라서 Protocol 로 공통 시그니처를 정의하고, 각 provider 는 구현체로 분리.

================================================================================
응답 포맷 통일
================================================================================
업체별 JSON 필드명이 다르므로 (`MMSI` vs `mmsi` vs `mmsiNumber`) 구현체 안에서
우리 포맷으로 변환한다:
  - `VesselProfile` — 식별자 + 스펙
  - `VesselPositionReport` — 실시간 위치

이렇게 하면 task / service 는 "누가 실제 제공자인지" 모르고도 동작한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, Sequence


@dataclass(frozen=True)
class VesselProfile:
    """AIS provider 에서 받은 선박 프로필 (식별자 + 스펙).

    None 값은 제공자가 안 줬다는 뜻. 우리 DB 에 저장 시 기존 값이 있으면 덮지
    않게 Service 가 병합 전략을 쓴다.
    """

    mmsi: Optional[str]
    imo_number: Optional[str]
    name: str
    flag: Optional[str] = None
    call_sign: Optional[str] = None
    length_m: Optional[int] = None
    breadth_m: Optional[int] = None
    gross_tonnage: Optional[int] = None
    vessel_type_code: Optional[int] = None
    year_built: Optional[int] = None
    owner: Optional[str] = None


@dataclass(frozen=True)
class VesselPositionReport:
    """단일 선박의 최신 AIS 위치.

    `poll_fleet_positions` 태스크가 provider 에 다수 MMSI 를 배치 조회하고
    결과를 이 형태로 받아 vessel_positions 테이블에 UPSERT.
    """

    mmsi: str
    latitude: float
    longitude: float
    speed_knots: Optional[float]
    heading_degrees: Optional[float]
    navigation_status: Optional[str]
    reported_at: Optional[datetime]


class AisProvider(Protocol):
    """모든 AIS provider 가 구현해야 하는 계약.

    두 가지 목적:
      1. **Vessel Search** — 이름 (또는 IMO) 으로 식별자 매핑 획득. 1회성,
         느리고 비쌈. 결과는 DB 영구 캐시.
      2. **Position Batch** — 이미 알고 있는 MMSI 배열에 대한 실시간 위치.
         주기적 (5~15분), 빠르고 상대적으로 저렴.
    """

    async def search_vessel_by_name(
        self,
        name: str,
        *,
        imo_number: Optional[str] = None,
    ) -> Optional[VesselProfile]:
        """이름 (또는 IMO) 으로 선박 프로필 1건 조회.

        동명 선박이 여러 척일 때 제공자가 어떤 매칭 로직을 쓰는지는 구현체에
        따름. IMO 가 주어지면 그것을 우선 사용.
        찾지 못하면 None.
        """
        ...

    async def get_positions(
        self,
        mmsis: Sequence[str],
    ) -> list[VesselPositionReport]:
        """다수 MMSI 에 대한 최신 위치 배치 조회.

        - rate limit 고려해 provider 가 내부적으로 분할/직렬화 가능.
        - 응답 없는 MMSI (AIS 신호 끊김) 는 결과에서 누락돼 돌아옴 (에러 아님).
        - 빈 리스트 입력 시 빈 리스트 반환.
        """
        ...
