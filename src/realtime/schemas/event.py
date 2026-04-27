# src/realtime/schemas/event.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from common.schemas.base import ResponseSchema as BaseSchema


class RealtimeEvent(BaseSchema):
    """team 별 실시간 이벤트 envelope (Redis pub/sub + WebSocket)."""
    type: str
    team_id: int
    actor_id: int | None = None
    payload: dict[str, Any] | None = None
    occurred_at: datetime

    @classmethod
    def now(
        cls,
        *,
        type: str,
        team_id: int,
        actor_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> "RealtimeEvent":
        return cls(
            type=type, team_id=team_id, actor_id=actor_id,
            payload=payload, occurred_at=datetime.now(timezone.utc),
        )
