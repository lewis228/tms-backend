# src/realtime/emit.py
"""도메인 service → WS entity 이벤트 발행 공용 헬퍼.

leg/service.py 의 인라인 패턴을 공용화: 발행 실패가 본 트랜잭션/응답에
영향을 주지 않도록 전부 삼킨다(log 는 realtime.service.publish 가 담당).
FE websocket-provider 가 type prefix 로 쿼리 캐시를 무효화한다.
"""
from __future__ import annotations
from typing import Any

from realtime.service import publish
from realtime.schemas.event import RealtimeEvent


async def emit_entity_event(
    event_type: str,
    team_id: int,
    payload: dict[str, Any] | None = None,
    actor_id: int | None = None,
) -> None:
    """예: emit_entity_event("rate_group.updated", team_id, {"rateGroupId": 3}, actor_id)."""
    try:
        await publish(RealtimeEvent.now(
            type=event_type, team_id=team_id, actor_id=actor_id, payload=payload,
        ))
    except Exception:  # noqa: BLE001 — 이벤트는 best-effort
        pass
