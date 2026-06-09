# src/realtime/v3_publish.py
"""v3 Container-First 도메인의 라이프사이클 이벤트 publish helper.

각 v3 service 의 create/update/delete 직후 호출. 실패해도 비즈니스 로직 막지 않음.
"""
from __future__ import annotations
from typing import Any

import structlog

from realtime.service import publish
from realtime.schemas.event import RealtimeEvent

log = structlog.get_logger(__name__)


async def safe_publish(*, type: str, team_id: int, actor_id: int | None = None,
                      payload: dict[str, Any] | None = None) -> None:
    try:
        await publish(RealtimeEvent.now(
            type=type, team_id=team_id, actor_id=actor_id, payload=payload,
        ))
    except Exception as e:  # noqa: BLE001
        log.warning("v3.publish_failed", error=str(e), type=type)


# 이벤트 타입 상수 (프론트가 매칭하는 키)
EVT_CONTAINER_STOP_CREATED = "container_stop.created"
EVT_CONTAINER_STOP_UPDATED = "container_stop.updated"
EVT_CONTAINER_STOP_DELETED = "container_stop.deleted"

EVT_LEG_SEGMENT_CREATED = "leg_segment.created"
EVT_LEG_SEGMENT_UPDATED = "leg_segment.updated"
EVT_LEG_SEGMENT_DELETED = "leg_segment.deleted"

EVT_CONTAINER_STATE_CHANGED = "container.state_changed"
# 재설계: 구 leg_rate/leg_charge/rate_quote/rate_tariff/distance_matrix 제거 → 해당 이벤트 상수 삭제.
