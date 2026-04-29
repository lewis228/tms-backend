# src/distance_matrix/providers.py
"""v3 거리 측정 어댑터.

OSRM / Google / Manual 중 team 설정으로 선택.
- ManualProvider: 좌표 haversine + 평균 속도 가정. 외부 호출 없음.
- OSRMProvider: 공개 OSRM 또는 자체 호스팅 OSRM HTTP 호출.
- GoogleProvider: 추후 (API key 필요).

team.distance_provider_config (JSON 문자열) 로 endpoint URL 등 설정.
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass

import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass
class DistanceResult:
    distance_value: float   # 단위 무관 (team.distance_unit_label 가 표시 라벨)
    duration_min: float
    source: str             # "OSRM" | "GOOGLE" | "MANUAL" | "CACHED"


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    la1, lo1, la2, lo2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dla, dlo = la2 - la1, lo2 - lo1
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


class ManualProvider:
    """좌표 기반 haversine. 외부 API 호출 없음."""
    name = "MANUAL"

    async def measure(self, o_lat: float, o_lng: float, d_lat: float, d_lng: float) -> DistanceResult:
        km = haversine_km(o_lat, o_lng, d_lat, d_lng)
        return DistanceResult(
            distance_value=km,
            duration_min=(km / 50.0) * 60.0,
            source="MANUAL",
        )


class OSRMProvider:
    """OSRM `route` API 호출.

    config 예시:
        {"endpoint": "https://router.project-osrm.org"}
        {"endpoint": "http://localhost:5000"}  # 자체 호스팅

    응답에서 routes[0].distance (meters), routes[0].duration (seconds) 사용.
    실패 시 ManualProvider 로 fallback.
    """
    name = "OSRM"

    def __init__(self, endpoint: str = "https://router.project-osrm.org", timeout: float = 5.0):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    async def measure(self, o_lat: float, o_lng: float, d_lat: float, d_lng: float) -> DistanceResult:
        url = f"{self.endpoint}/route/v1/driving/{o_lng},{o_lat};{d_lng},{d_lat}"
        params = {"overview": "false", "alternatives": "false", "steps": "false"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                raise RuntimeError(f"OSRM bad response: {data.get('code')}")
            r = data["routes"][0]
            distance_m = float(r["distance"])
            duration_s = float(r["duration"])
            return DistanceResult(
                distance_value=distance_m / 1000.0,  # km
                duration_min=duration_s / 60.0,
                source="OSRM",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("osrm.measure_failed", error=str(e))
            # haversine fallback
            return await ManualProvider().measure(o_lat, o_lng, d_lat, d_lng)


def get_provider(name: str | None, config_json: str | None = None):
    name = (name or "MANUAL").upper()
    config: dict = {}
    if config_json:
        try:
            config = json.loads(config_json)
        except Exception:  # noqa: BLE001
            config = {}
    if name == "OSRM":
        endpoint = config.get("endpoint") or "https://router.project-osrm.org"
        return OSRMProvider(endpoint=endpoint)
    # GOOGLE 어댑터는 별도 PR. 일단 Manual 로 fallback.
    return ManualProvider()
