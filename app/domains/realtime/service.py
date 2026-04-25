"""Realtime — Redis Pub/Sub publish + subscribe.

채널 키: tms:tenant:{tenant_id}:events
"""
from __future__ import annotations

import json
from typing import AsyncIterator

from app.core.redis import get_redis
from app.domains.realtime.schema import RealtimeEvent


def _channel(tenant_id: str) -> str:
    return f"tms:tenant:{tenant_id}:events"


async def publish(event: RealtimeEvent) -> int:
    r = get_redis()
    return await r.publish(_channel(event.tenant_id), event.model_dump_json(by_alias=True))


async def subscribe_stream(tenant_id: str) -> AsyncIterator[str]:
    """비동기 제너레이터 — SSE 라우터가 그대로 yield."""
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(tenant_id))
    try:
        async for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            data = msg.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            yield data
    finally:
        await pubsub.unsubscribe(_channel(tenant_id))
        await pubsub.aclose()


def serialize_payload(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False)
