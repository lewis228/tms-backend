"""팀 scoped 이벤트 publisher.

scraping 워커 / FastAPI 핸들러 어느 쪽에서든 호출 가능. 같은 메시지 포맷으로
Redis pub/sub 채널 `team:{team_id}:events` 에 JSON 발행한다.

WebSocket 바운드리 (ws_router.py) 에서 이 채널을 subscribe 해 접속된 클라이언트로
전파한다. 채팅 / 알림 등 향후 확장은 채널명만 추가하면 된다:
  - team:{team_id}:events         (shipment 이벤트)
  - user:{user_id}:notifications  (개인 알림)
  - chat:room:{room_id}           (채팅)
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def team_events_channel(team_id: int) -> str:
    """팀 scoped 이벤트 채널 이름."""
    return f"team:{team_id}:events"


def build_event_message(
    event_type: str,
    team_id: int,
    payload: dict[str, Any],
) -> str:
    """표준 이벤트 메시지 JSON 생성.

    형식:
      { "type": "shipment.status.changed",
        "timestamp": "2026-04-20T15:30:00Z",
        "team_id": 1,
        "payload": {...} }
    """
    return json.dumps(
        {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "team_id": team_id,
            "payload": payload,
        },
        default=str,  # datetime 등 비-JSON 객체 안전 직렬화
    )


async def publish_team_event(
    redis: Redis,
    team_id: int,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """팀 채널로 이벤트 발행. Redis 장애 시 로그만 남기고 삼킨다
    (이벤트 발행 실패가 본 흐름을 깨면 안 됨).
    """
    try:
        channel = team_events_channel(team_id)
        message = build_event_message(event_type, team_id, payload)
        await redis.publish(channel, message)
    except Exception:  # noqa: BLE001
        logger.exception(
            "publish_team_event_failed team_id=%s type=%s", team_id, event_type
        )
