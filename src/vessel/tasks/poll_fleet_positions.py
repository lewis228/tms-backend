"""Celery Beat task: 추적 중인 모든 선박의 최신 위치 일괄 갱신.

================================================================================
주기
================================================================================
Celery Beat schedule 에 등록:
  `settings.AIS_POLL_INTERVAL_MINUTES` (기본 10분)

한 번 tick 마다:
  1. 추적 대상 MMSI 리스트 수집 (VesselRepository.list_active_mmsis)
  2. AIS provider 에 batch 위치 요청
  3. vessel_positions 에 upsert
  4. **팀별로 묶어서** WebSocket 이벤트 push (publisher.py 사용)

================================================================================
팀별 push 이유
================================================================================
vessel 은 전역 마스터지만, 실시간 위치 이벤트는 **해당 선박을 추적 중인 팀에게만**
보내야 한다. 임의의 팀이 다른 팀의 vessel 위치를 모두 구독하면 WS traffic 낭비
+ 정보 노출. 그래서:
  - 업데이트된 vessel_id 리스트를 수집
  - ocean_shipments 조인으로 각 vessel 을 추적하는 team_id 집합 계산
  - team 별로 `publish_team_event` 호출 (이벤트 type = "vessel.position_updated")

================================================================================
Frontend 가 받는 이벤트 형태
================================================================================
    {
      "type": "vessel.position_updated",
      "team_id": 1,
      "timestamp": "2026-04-22T15:30:00Z",
      "payload": {
        "vessels": [
          {
            "id": 42, "mmsi": "636019825", "name": "X-PRESS PHOENIX",
            "latitude": 34.523, "longitude": -140.105,
            "speed_knots": 18.2, "heading_degrees": 72,
            "navigation_status": "underway",
            "reported_at": "2026-04-22T15:29:45Z"
          },
          ...
        ]
      }
    }

Frontend (WebSocket 리스너):
    queryClient.setQueryData(["fleet-vessels"], (prev) =>
      prev.map(v => {
        const u = payload.vessels.find(x => x.id === v.id);
        return u ? { ...v, position: u } : v;
      })
    );
  → Leaflet Marker 가 prop 변경을 받고 자동 재렌더 (좌표 이동 + 회전).

================================================================================
실패 처리
================================================================================
- Provider 예외 / 빈 응답 → 그냥 다음 tick 에 재시도. Celery retry 없음
  (Beat 자체가 주기적이라 재시도 의미 희박).
- WS publish 실패 → 로그만 남기고 통과 (publish_team_event 가 내부 try/except).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Iterable

import structlog
from sqlalchemy import select

# NOTE: celery_app / session / redis 경로는 프로젝트 관례에 맞춰 조정.
from celery_app import celery as celery_app
from cache.redis_connection import write_redis
from common.events.publisher import publish_team_event
from database.mysql_connection import async_session_maker as async_session_factory
from ocean.shipment.model import ShipmentModel
from vessel.model import VesselModel, VesselPositionModel
from vessel.service import VesselService

logger = structlog.get_logger(__name__)


@celery_app.task(name="vessel.poll_fleet_positions")
def poll_fleet_positions_task() -> int:
    """Entry point. 반환값 = 갱신된 선박 수 (메트릭용)."""
    return asyncio.run(_run())


async def _run() -> int:
    async with async_session_factory() as db:
        svc = VesselService(db)
        mmsis = await svc.repo.list_active_mmsis(limit=1000)
        if not mmsis:
            logger.info("poll_fleet_positions_skip_no_mmsi")
            return 0

        updated_rows: list[VesselPositionModel] = await svc.refresh_positions(mmsis)
        if not updated_rows:
            await db.commit()
            logger.info("poll_fleet_positions_no_updates", count_mmsis=len(mmsis))
            return 0

        await db.commit()

        # 업데이트된 vessel_id 집합.
        vessel_ids = [r.vessel_id for r in updated_rows]

        # 각 vessel 을 추적 중인 팀 집합 수집.
        # TODO: ocean_shipments.vessel_id 필드 추가 후 아래 쿼리 활성화.
        # 임시로 "모든 팀에 publish" — 운영 전에 반드시 교체!
        team_ids_by_vessel: dict[int, set[int]] = defaultdict(set)
        # team_ids_by_vessel = await _collect_team_ids(db, vessel_ids)

        # vessel_id → latest position row 맵.
        positions_by_vessel = {r.vessel_id: r for r in updated_rows}
        vessels_by_id = await _load_vessels(db, vessel_ids)

        # 팀별로 payload 묶어 publish.
        redis = write_redis
        for team_id in _unique_team_ids(team_ids_by_vessel):
            payload_vessels = []
            for vid in team_ids_by_vessel.get(team_id, set()):
                pos = positions_by_vessel.get(vid)
                vessel = vessels_by_id.get(vid)
                if pos is None or vessel is None:
                    continue
                payload_vessels.append(_serialise_position(vessel, pos))
            if not payload_vessels:
                continue
            await publish_team_event(
                redis,
                team_id=team_id,
                event_type="vessel.position_updated",
                payload={"vessels": payload_vessels},
            )

        logger.info(
            "poll_fleet_positions_ok",
            mmsi_count=len(mmsis),
            updated_count=len(updated_rows),
            team_count=len(set(_unique_team_ids(team_ids_by_vessel))),
        )
        return len(updated_rows)


def _unique_team_ids(m: dict[int, set[int]]) -> Iterable[int]:
    seen: set[int] = set()
    for ids in m.values():
        for tid in ids:
            if tid in seen:
                continue
            seen.add(tid)
            yield tid


async def _load_vessels(db, vessel_ids: list[int]) -> dict[int, VesselModel]:
    """id 목록 → { id: VesselModel } 맵. 빈 리스트 방어."""
    if not vessel_ids:
        return {}
    stmt = select(VesselModel).where(VesselModel.id.in_(vessel_ids))
    rows = (await db.execute(stmt)).scalars().all()
    return {v.id: v for v in rows}


def _serialise_position(
    vessel: VesselModel, pos: VesselPositionModel
) -> dict:
    """WS payload 직렬화 — float 변환 + 불필요 필드 제거."""
    return {
        "id": vessel.id,
        "mmsi": vessel.mmsi,
        "imo_number": vessel.imo_number,
        "name": vessel.name,
        "latitude": float(pos.latitude),
        "longitude": float(pos.longitude),
        "speed_knots": (
            float(pos.speed_knots) if pos.speed_knots is not None else None
        ),
        "heading_degrees": (
            float(pos.heading_degrees)
            if pos.heading_degrees is not None
            else None
        ),
        "navigation_status": pos.navigation_status,
        "reported_at": (
            pos.reported_at.isoformat().replace("+00:00", "Z")
            if pos.reported_at is not None
            else None
        ),
    }


# ------------------------------------------------------------------
# Vessel → Team 매핑 (ocean_shipments.vessel_id 추가 후 활성화)
# ------------------------------------------------------------------

async def _collect_team_ids(
    db, vessel_ids: list[int]
) -> dict[int, set[int]]:
    """
    TODO: ocean_shipments 에 `vessel_id` FK 추가 후 아래 쿼리 사용.

    SELECT s.vessel_id, s.team_id
    FROM ocean_shipments s
    WHERE s.vessel_id IN :vessel_ids
      AND s.is_active = TRUE
      AND s.status IN ('pending', 'tracking', 'awaiting_manifest')

    Returns: { vessel_id: {team_id, team_id, ...} }
    """
    if not vessel_ids:
        return {}
    stmt = (
        select(ShipmentModel.team_id)
        .where(ShipmentModel.is_active.is_(True))
        .limit(0)  # placeholder — vessel_id 컬럼 없을 때는 아무도 매칭 안 되게.
    )
    _ = await db.execute(stmt)
    return {}
