"""Realtime — WebSocket ConnectionManager + Redis Pub/Sub.

브로드캐스트 모델:
  도메인 코드 → publish(event)
                 ↓ Redis PUBLISH (채널: tms:tenant:{tenant_id}:events)
                 ↓
  ConnectionManager (워커별 1개) — Redis SUBSCRIBE 유지
                 ↓ 메시지 수신
                 ↓ 해당 tenant 의 활성 WS 들에 enqueue
                 ↓ 각 WS 의 send-loop 가 큐에서 꺼내 send_text

장점: 멀티 워커/포드 fan-out, 단일 워커 내 다중 연결 효율적, send queue 사이즈 제한으로 backpressure.

Close codes (4xxx 일반 범위):
- 4001: 토큰 만료
- 4002: 토큰 무효 / 해독 실패
- 4003: tenant 미해결 (SUPER_ADMIN tenant 헤더 미지정 등)
- 4004: ping idle timeout (60s pong 없음)
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.domains.realtime.schema import RealtimeEvent

log = get_logger("realtime")

# WS 별 outbound 큐 사이즈. 폭주 시 oldest drop.
SEND_QUEUE_MAXSIZE = 1000


def channel_for(tenant_id: str) -> str:
    return f"tms:tenant:{tenant_id}:events"


async def publish(event: RealtimeEvent, *, db: Any | None = None) -> int:
    """도메인 → Redis (실시간) + 옵션으로 inbox fan-out.

    db 가 주어지면 notifications 도메인의 fan_out_event 를 호출해 tenant 의
    ADMIN+DISPATCHER 의 inbox 에 row 를 생성한다. actor_id 본인은 제외.
    Redis 미설정 / 다운 시 예외 흡수 (도메인 비즈니스 로직 보호).
    """
    if db is not None:
        # 순환 import 회피 — realtime 모듈 로드 시점에 notifications 가 아직 미초기화일 수 있음.
        from app.domains.notifications.service import fan_out_event
        try:
            await fan_out_event(db, event)
        except Exception as e:  # noqa: BLE001
            log.warning("realtime.fanout_failed", error=str(e), type=event.type)
    try:
        r = get_redis()
        return await r.publish(channel_for(event.tenant_id), event.model_dump_json(by_alias=True))
    except Exception as e:  # noqa: BLE001
        log.warning("realtime.publish_failed", error=str(e), type=event.type)
        return 0


class _Connection:
    """단일 WebSocket 연결 — outbound 큐 + send-loop."""

    __slots__ = ("ws", "tenant_id", "user_id", "queue", "dropped")

    def __init__(self, ws, tenant_id: str, user_id: str) -> None:
        self.ws = ws
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SEND_QUEUE_MAXSIZE)
        self.dropped = 0

    def offer(self, raw: str) -> None:
        """비동기 enqueue 시도. 큐가 가득차면 oldest drop + 경고."""
        try:
            self.queue.put_nowait(raw)
        except asyncio.QueueFull:
            try:
                _ = self.queue.get_nowait()
                self.dropped += 1
                self.queue.put_nowait(raw)
                log.warning(
                    "realtime.send_queue_overflow",
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    dropped=self.dropped,
                )
            except Exception:  # noqa: BLE001
                pass


class ConnectionManager:
    """워커 내 활성 WS 등록부. Redis 구독은 tenant 처음 등록되는 시점에 시작."""

    def __init__(self) -> None:
        self._by_tenant: dict[str, set[_Connection]] = {}
        self._subscriber_tasks: dict[str, asyncio.Task] = {}
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

    def fanout(self, tenant_id: str, raw: str) -> None:
        for conn in list(self._by_tenant.get(tenant_id, ())):
            conn.offer(raw)

    async def _tenant_subscriber(self, tenant_id: str) -> None:
        """이 tenant 첫 연결 등록 시 시작, 마지막 연결 해제 시 종료."""
        ch = channel_for(tenant_id)
        try:
            r = get_redis()
            pubsub = r.pubsub()
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
            log.error("realtime.subscriber_crashed", tenant_id=tenant_id, error=str(e))

    def stats(self) -> dict[str, Any]:
        return {
            "tenants": len(self._by_tenant),
            "connections": sum(len(s) for s in self._by_tenant.values()),
        }


# 워커 프로세스 싱글턴
manager = ConnectionManager()
