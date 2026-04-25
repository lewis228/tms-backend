"""Realtime 이벤트 스키마 — Redis Pub/Sub payload 형식."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.schema import BaseSchema


class RealtimeEvent(BaseSchema):
    type: str
    tenant_id: str
    actor_id: str | None = None
    payload: dict[str, Any] | None = None
    occurred_at: datetime

    @classmethod
    def now(
        cls,
        *,
        type: str,
        tenant_id: str,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> "RealtimeEvent":
        return cls(
            type=type,
            tenant_id=tenant_id,
            actor_id=actor_id,
            payload=payload,
            occurred_at=datetime.now(timezone.utc),
        )
