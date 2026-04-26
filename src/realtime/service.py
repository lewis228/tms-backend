# src/realtime/service.py
"""Realtime — WebSocket ConnectionManager + Redis Pub/Sub fan-out.

브로드캐스트:
  도메인 코드 → publish(event)
                 ↓ Redis PUBLISH (채널: tms:tenant:{tenant_id}:events)
                 ↓
  ConnectionManager (워커별 1개) — Redis SUBSCRIBE 유지
                 ↓ 수신 → 해당 tenant 의 활성 WS 들에 enqueue
                 ↓ 각 WS send-loop 가 send_text

Close codes (4xxx):
- 4001: 토큰 만료
- 4002: 토큰 무효
- 4003: tenant 미해결
- 4004: ping idle timeout
"""
from __future__ import annotations
import asyncio
import contextlib
from typing import Any

import structlog

from cache.redis_connection import redis as default_redis
from realtime.schemas.event import RealtimeEvent

log = structlog.get_logger(__name__)

SEND_QUEUE_MAXSIZE = 1000


def channel_for(tenant_id: int) -> str:
    return f"tms:tenant:{tenant_id}:events"


async def publish(event: RealtimeEvent, *, db: Any | None = None) -> int:
    """도메인 → Redis. fan_out 도메인 (notification inbox) 추후 wiring."""
    try:
        return await default_redis.publish(
            channel_for(event.tenant_id),
            event.model_dump_json(by_alias=True),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("realtime.publish_failed", error=str(e), type=event.type)
        return 0


class _Connection:
    __slots__ = ("ws", "tenant_id", "user_id", "queue", "dropped")

    def __init__(self, ws, tenant_id: int, user_id: int) -> None:
        self.ws = ws
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SEND_QUEUE_MAXSIZE)
        self.dropped = 0

    def offer(self, raw: str) -> None:
        try:
            self.queue.put_nowait(raw)
        except asyncio.QueueFull:
            with contextlib.suppress(Exception):
                _ = self.queue.get_nowait()
                self.dropped += 1
                self.queue.put_nowait(raw)
                log.warning("realtime.queue_overflow",
                            tenant_id=self.tenant_id, dropped=self.dropped)


class ConnectionManager:
    """워커 내 활성 WS 등록부."""

    def __init__(self) -> None:
        self._by_tenant: dict[int, set[_Connection]] = {}
        self._subscriber_tasks: dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, conn: _Connection) -> None:
        async with self._lock:
            conns = self._by_tenant.setdefault(conn.tenant_id, set())
            conns.add(conn)
            if conn.tenant_id not in self._subscriber_tasks:
                task = asyncio.create_task(
                    self._tenant_subscriber(conn.tenant_id),
                    name=f"realtime-sub-{conn.tenant_id}",
                )
                self._subscriber_tasks[conn.tenant_id] = task

    async def unregister(self, conn: _Connection) -> None:
        async with self._lock:
            conns = self._by_tenant.get(conn.tenant_id)
            if conns:
                conns.discard(conn)
                if not conns:
                    self._by_tenant.pop(conn.tenant_id, None)
                    task = self._subscriber_tasks.pop(conn.tenant_id, None)
                    if task and not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

    def fanout(self, tenant_id: int, raw: str) -> None:
        for conn in list(self._by_tenant.get(tenant_id, ())):
            conn.offer(raw)

    async def _tenant_subscriber(self, tenant_id: int) -> None:
        ch = channel_for(tenant_id)
        try:
            pubsub = default_redis.pubsub()
            await pubsub.subscribe(ch)
            try:
                async for msg in pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    data = msg.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    self.fanout(tenant_id, data)
            finally:
                with contextlib.suppress(Exception):
                    await pubsub.unsubscribe(ch)
                with contextlib.suppress(Exception):
                    await pubsub.aclose()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.error("realtime.subscriber_crashed",
                      tenant_id=tenant_id, error=str(e))

    def stats(self) -> dict[str, Any]:
        return {
            "tenants": len(self._by_tenant),
            "connections": sum(len(s) for s in self._by_tenant.values()),
        }


manager = ConnectionManager()
