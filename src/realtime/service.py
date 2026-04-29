# src/realtime/service.py
"""Realtime — WebSocket ConnectionManager + Redis Pub/Sub fan-out.

브로드캐스트:
  도메인 코드 → publish(event)
                 ↓ Redis PUBLISH (채널: tms:team:{team_id}:events)
                 ↓
  ConnectionManager (워커별 1개) — Redis SUBSCRIBE 유지
                 ↓ 수신 → 해당 team 의 활성 WS 들에 enqueue
                 ↓ 각 WS send-loop 가 send_text

Close codes (4xxx):
- 4001: 토큰 만료
- 4002: 토큰 무효
- 4003: team 미해결
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


def channel_for(team_id: int) -> str:
    return f"tms:team:{team_id}:events"


async def publish(event: RealtimeEvent, *, db: Any | None = None) -> int:
    """도메인 → Redis + (db 가 주어지면) notification inbox fan-out.

    db 인자를 넘기면 `notification.fan_out_event` 가 호출되어 inbox row 생성.
    db 없이 호출하면 Redis publish 만 (예: 백그라운드 task 등 세션 없는 컨텍스트).
    """
    # 1) Redis publish (실시간 WS push)
    try:
        published = await default_redis.publish(
            channel_for(event.team_id),
            event.model_dump_json(by_alias=True),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("realtime.publish_failed", error=str(e), type=event.type)
        published = 0

    # 2) Notification inbox fan-out (db 주어진 경우만)
    if db is not None:
        try:
            from notification.fan_out import fan_out_event
            await fan_out_event(db, event)
        except Exception as e:  # noqa: BLE001
            log.warning("notification.fan_out_failed", error=str(e), type=event.type)
            # 세션 invalid 상태 방지 — fan_out 실패 시 그 부분 rollback
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass

    return published


class _Connection:
    __slots__ = ("ws", "team_id", "user_id", "queue", "dropped")

    def __init__(self, ws, team_id: int, user_id: int) -> None:
        self.ws = ws
        self.team_id = team_id
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
                            team_id=self.team_id, dropped=self.dropped)


class ConnectionManager:
    """워커 내 활성 WS 등록부."""

    def __init__(self) -> None:
        self._by_team: dict[int, set[_Connection]] = {}
        self._subscriber_tasks: dict[int, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, conn: _Connection) -> None:
        async with self._lock:
            conns = self._by_team.setdefault(conn.team_id, set())
            conns.add(conn)
            if conn.team_id not in self._subscriber_tasks:
                task = asyncio.create_task(
                    self._team_subscriber(conn.team_id),
                    name=f"realtime-sub-{conn.team_id}",
                )
                self._subscriber_tasks[conn.team_id] = task

    async def unregister(self, conn: _Connection) -> None:
        async with self._lock:
            conns = self._by_team.get(conn.team_id)
            if conns:
                conns.discard(conn)
                if not conns:
                    self._by_team.pop(conn.team_id, None)
                    task = self._subscriber_tasks.pop(conn.team_id, None)
                    if task and not task.done():
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

    def fanout(self, team_id: int, raw: str) -> None:
        for conn in list(self._by_team.get(team_id, ())):
            conn.offer(raw)

    async def _team_subscriber(self, team_id: int) -> None:
        ch = channel_for(team_id)
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
                    self.fanout(team_id, data)
            finally:
                with contextlib.suppress(Exception):
                    await pubsub.unsubscribe(ch)
                with contextlib.suppress(Exception):
                    await pubsub.aclose()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.error("realtime.subscriber_crashed",
                      team_id=team_id, error=str(e))

    def stats(self) -> dict[str, Any]:
        return {
            "teams": len(self._by_team),
            "connections": sum(len(s) for s in self._by_team.values()),
        }

    async def shutdown(self) -> None:
        """앱 종료 시: 모든 subscriber task 취소 + 등록부 정리.

        활성 WS 자체는 endpoint 의 finally 가 unregister 함.
        여기서는 워커 내부 background task 만 정리.
        """
        async with self._lock:
            tasks = list(self._subscriber_tasks.values())
            self._subscriber_tasks.clear()
            self._by_team.clear()
        for t in tasks:
            if not t.done():
                t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t


manager = ConnectionManager()
