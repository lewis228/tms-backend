"""개발 / 테스트용 mock AIS provider.

================================================================================
역할
================================================================================
진짜 AIS 업체 API 키가 없을 때도 전체 파이프라인(resolve → position → WS push
→ 프론트 갱신)이 end-to-end 로 돌아가는지 확인할 수 있게 해준다.
  - `AIS_PROVIDER=mock` 이면 자동 선택됨 (factory.py 참조)
  - 실제 네트워크 호출 없음 — 임의 데이터 in-memory 반환
  - `search_vessel_by_name` 은 선박 이름 기반으로 결정적인 mock MMSI 생성
    (해시 → 9자리 숫자) — 같은 이름 넣으면 항상 같은 MMSI
  - `get_positions` 는 태평양 / 인도양 주변을 랜덤워크시킴 — 호출할 때마다
    약간씩 좌표가 움직여서 프론트 실시간 갱신 효과 확인 가능
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Optional, Sequence

from vessel.ais.base import AisProvider, VesselPositionReport, VesselProfile


# 선박 이름 → (lat, lng) 앵커. 호출마다 이 앵커 주변으로 소량 이동.
# 실제 AIS 연결 전까지 프론트 마커가 살아 움직이는 것처럼 보이려는 장치.
_POSITION_ANCHORS: dict[str, tuple[float, float]] = {}


def _deterministic_mmsi(seed: str) -> str:
    """문자열 → 9자리 MMSI (0~999999999). SHA1 해시를 모듈로 분할."""
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    value = int(digest[:12], 16) % 1_000_000_000
    return f"{value:09d}"


def _deterministic_imo(seed: str) -> str:
    """문자열 → 7자리 IMO. 실제 check digit 규칙은 무시 (mock 이므로)."""
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    value = int(digest[12:20], 16) % 10_000_000
    return f"{value:07d}"


class MockAisProvider(AisProvider):
    async def search_vessel_by_name(
        self,
        name: str,
        *,
        imo_number: Optional[str] = None,
    ) -> Optional[VesselProfile]:
        # 빈 이름은 실패 간주. 빈 결과 응답으로 에러 분기 테스트 가능하게 설계.
        if not name or not name.strip():
            return None
        normalised = name.strip().upper()
        mmsi = _deterministic_mmsi(normalised)
        imo = imo_number or _deterministic_imo(normalised)
        return VesselProfile(
            mmsi=mmsi,
            imo_number=imo,
            name=normalised,
            flag="XX",
            call_sign=None,
            length_m=220,
            breadth_m=32,
            gross_tonnage=88000,
            vessel_type_code=70,  # Cargo
            year_built=2018,
            owner="Mock Shipping Co.",
        )

    async def get_positions(
        self, mmsis: Sequence[str]
    ) -> list[VesselPositionReport]:
        now = datetime.now(timezone.utc)
        results: list[VesselPositionReport] = []
        for mmsi in mmsis:
            anchor = _POSITION_ANCHORS.get(mmsi)
            if anchor is None:
                # 시드 기반으로 Pacific / Indian ocean 어딘가 앵커 세팅.
                rng = random.Random(int(mmsi))
                lat = rng.uniform(-10, 45)
                lng = rng.uniform(-160, 160)
                anchor = (lat, lng)
                _POSITION_ANCHORS[mmsi] = anchor
            # 앵커 주변 랜덤워크 (지구 위에서 0.05° ≈ 5km)
            lat = anchor[0] + random.uniform(-0.05, 0.05)
            lng = anchor[1] + random.uniform(-0.05, 0.05)
            _POSITION_ANCHORS[mmsi] = (lat, lng)
            results.append(
                VesselPositionReport(
                    mmsi=mmsi,
                    latitude=lat,
                    longitude=lng,
                    speed_knots=round(random.uniform(10, 22), 1),
                    heading_degrees=round(random.uniform(0, 359.9), 1),
                    navigation_status="underway",
                    reported_at=now,
                )
            )
        return results
