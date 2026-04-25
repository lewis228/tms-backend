"""MarineTraffic AIS provider 구현 (STUB — 실제 과금 계정 연결 시 활성화).

================================================================================
WHEN TO ENABLE
================================================================================
1. MarineTraffic 계정 생성 + API key 발급 (https://servicedocs.marinetraffic.com)
2. `.env` / AWS Parameter Store 에 추가:
      AIS_PROVIDER=marinetraffic
      AIS_API_KEY=<your-key>
3. 재시작. factory.py 가 자동으로 이 provider 를 선택.

================================================================================
HOW IT WORKS
================================================================================
공식 REST API 엔드포인트 2개를 호출:

  1. Vessel Search API (이름 → MMSI / IMO 매핑)
     GET https://services.marinetraffic.com/api/vesselsearch/v:3/{API_KEY}
         ?shipname=X-PRESS+PHOENIX
     응답: [{ MMSI, IMO, SHIPNAME, SHIPTYPE, FLAG, ... }]
     호출당 과금. 결과는 우리 DB 영구 캐시 (vessels 테이블).

  2. Vessel Position (MMSI → 실시간 좌표)
     GET https://services.marinetraffic.com/api/exportvessel/v:8/{API_KEY}
         ?mmsi=636019825,525019101,...&protocol=jsono
     응답: [{ MMSI, LAT, LON, SPEED, COURSE, STATUS, TIMESTAMP, ... }]
     호출당 과금 / 또는 credits 구독. 여러 MMSI 한 번에 조회 가능 (배치).

================================================================================
DESIGN NOTES
================================================================================
- **httpx.AsyncClient 재사용** — task 단위로 만들고 context manager 로 정리.
- **Retry 정책** — 4xx (client error) 는 재시도 안 함. 5xx/timeout 은 태스크
  레벨 재시도 (Celery retry). 여기서는 1회만 호출.
- **Rate limit** — 서버가 주는 `Retry-After` 헤더 존중. 우리가 선제적으로
  분당 호출 수를 제한하려면 Redis 키 기반 토큰버킷을 추가할 수 있다.
- **SHIPTYPE → vessel_type_code** 은 그대로 보관 (UI 에서 카테고리 변환).
- **TIMESTAMP** 는 MarineTraffic 이 "YYYY-MM-DD HH:MM:SS UTC" 로 주므로
  parsing 주의 (tz-aware datetime 으로 변환).

================================================================================
STATUS
================================================================================
🚧 미구현 — `NotImplementedError` raise. 구현 시 아래 TODO 섹션 따라가면 됨.
"""

from __future__ import annotations

from typing import Optional, Sequence

import httpx

from common.const.settings import settings
from vessel.ais.base import AisProvider, VesselPositionReport, VesselProfile


MARINETRAFFIC_BASE = "https://services.marinetraffic.com/api"


class MarineTrafficProvider(AisProvider):
    """MarineTraffic 실구현 플레이스홀더.

    TODO 체크리스트 (구현 시):
      [ ] settings.AIS_API_KEY 확인 (None 이면 ValueError)
      [ ] search_vessel_by_name — GET /vesselsearch/v:3/{key}?shipname=...
          응답 필드 매핑: MMSI → mmsi, IMO → imo_number, SHIPNAME → name, ...
          여러 건 반환 시 정확 일치 > 부분 일치 우선. IMO 입력 있으면 IMO 로
          이미 검색해서 1건만 받도록 파라미터 바꿀 수도 있음.
      [ ] get_positions — GET /exportvessel/v:8/{key}?mmsi=... (쉼표 구분)
          응답 필드: LAT → latitude, LON → longitude, SPEED (×10 정수 → /10),
          COURSE → heading_degrees, STATUS → navigation_status enum 매핑,
          TIMESTAMP → reported_at (UTC parse)
      [ ] `protocol=jsono` 파라미터로 JSON 응답 강제
      [ ] 한 번에 50~200 MMSI 묶어 호출 (업체 제한 확인)
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("AIS_API_KEY is required for MarineTrafficProvider")
        self._api_key = api_key

    async def search_vessel_by_name(
        self,
        name: str,
        *,
        imo_number: Optional[str] = None,
    ) -> Optional[VesselProfile]:
        # TODO: 아래 pseudo-code 를 실제 호출로 교체.
        #
        # async with httpx.AsyncClient(timeout=10) as client:
        #     resp = await client.get(
        #         f"{MARINETRAFFIC_BASE}/vesselsearch/v:3/{self._api_key}",
        #         params={
        #             "shipname": name,
        #             "protocol": "jsono",
        #             **({"imo": imo_number} if imo_number else {}),
        #         },
        #     )
        #     resp.raise_for_status()
        #     rows = resp.json()
        # if not rows:
        #     return None
        # row = rows[0]
        # return VesselProfile(
        #     mmsi=str(row.get("MMSI")) if row.get("MMSI") else None,
        #     imo_number=str(row.get("IMO")) if row.get("IMO") else None,
        #     name=row.get("SHIPNAME", name),
        #     flag=row.get("FLAG"),
        #     call_sign=row.get("CALLSIGN"),
        #     length_m=row.get("LENGTH"),
        #     breadth_m=row.get("BREADTH"),
        #     gross_tonnage=row.get("GROSS_TONNAGE"),
        #     vessel_type_code=row.get("SHIPTYPE"),
        #     year_built=row.get("YEAR_BUILT"),
        #     owner=row.get("OWNER"),
        # )
        raise NotImplementedError(
            "MarineTrafficProvider.search_vessel_by_name is not wired yet. "
            "Enable AIS_PROVIDER=mock for now, or implement the httpx call above."
        )

    async def get_positions(
        self, mmsis: Sequence[str]
    ) -> list[VesselPositionReport]:
        # TODO 샘플 구현 (주석만) — 교체해서 사용하라.
        #
        # if not mmsis:
        #     return []
        # # 100개 단위로 나눠서 호출
        # CHUNK = 100
        # results: list[VesselPositionReport] = []
        # async with httpx.AsyncClient(timeout=15) as client:
        #     for i in range(0, len(mmsis), CHUNK):
        #         chunk = mmsis[i : i + CHUNK]
        #         resp = await client.get(
        #             f"{MARINETRAFFIC_BASE}/exportvessel/v:8/{self._api_key}",
        #             params={
        #                 "mmsi": ",".join(chunk),
        #                 "protocol": "jsono",
        #             },
        #         )
        #         resp.raise_for_status()
        #         for row in resp.json():
        #             results.append(VesselPositionReport(
        #                 mmsi=str(row["MMSI"]),
        #                 latitude=float(row["LAT"]),
        #                 longitude=float(row["LON"]),
        #                 speed_knots=float(row["SPEED"]) / 10 if row.get("SPEED") else None,
        #                 heading_degrees=float(row["COURSE"]) if row.get("COURSE") else None,
        #                 navigation_status=_map_status_code(row.get("STATUS")),
        #                 reported_at=_parse_marinetraffic_timestamp(row.get("TIMESTAMP")),
        #             ))
        # return results
        raise NotImplementedError(
            "MarineTrafficProvider.get_positions is not wired yet. "
            "Enable AIS_PROVIDER=mock for now, or implement the httpx call above."
        )


# --- helper shells (구현 시 함께 작성) ---

def _map_status_code(code: Optional[int]) -> Optional[str]:
    """AIS Navigation Status (0~15) → 우리 UI 문자열.

    0=Under way using engine, 1=At anchor, 5=Moored, 6=Aground, 7=Fishing,
    8=Under way sailing, 9~14=기타, 15=Undefined.
    """
    if code is None:
        return None
    mapping = {
        0: "underway",
        1: "anchored",
        2: "not-under-command",
        3: "restricted",
        4: "draft-limited",
        5: "moored",
        6: "aground",
        7: "fishing",
        8: "underway",
    }
    return mapping.get(code, "unknown")
