"""프로세스(파드) 당 1개만 실행되는 Redis Pub/Sub 리스너.

팀 채널 ``team:*:events`` 를 **패턴 구독** 으로 한 번만 걸고, 수신한 메시지를
해당 팀에 접속된 모든 WebSocket 으로 ``ConnectionManager.broadcast_to_team``
을 통해 push 한다.

이전 구현(``_pump_redis_to_ws``)은 WS 연결 1개마다 subscribe 를 만들어서
Redis 구독자 수가 **접속 유저 수에 비례해 증가**했다. 이 구현으로
구독자 수는 **프로세스(파드) 수에 비례** — 오토스케일링 환경에서 Redis
로드가 유저 수 증가와 무관하게 선형으로 낮아진다.

아키텍처:
    EC2 N개 → 각 EC2 가 lifespan startup 에서 listener 1개 기동
        → Redis subscriber = N 개 (고정)
    publish 1회 → Redis 가 N 개 파드에 복제 전송
        → 각 파드의 ConnectionManager 가 자신에게 붙은 해당 팀 WS 에만 push

장애 처리:
    Redis 연결이 끊기면 지수 백오프로 재연결 + 재구독. 리스너 자체는 서버
    수명과 함께 살아있고 외부에서 Task.cancel() 만 죽음.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Final

from redis.asyncio import Redis

from common.events.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


# 팀 채널 패턴 — publisher (`publisher.team_events_channel`) 와 대칭.
_PATTERN: Final = "team:*:events"

# 재연결 백오프 (최소 1s, 최대 30s 캡).
_BACKOFF_MIN_SEC: Final = 1.0
_BACKOFF_MAX_SEC: Final = 30.0


class TeamEventsListener:
    """프로세스 전역 Redis 구독 → 팀 브로드캐스트 디스패처.

    사용:
        listener = TeamEventsListener(read_redis, connection_manager)
        task = asyncio.create_task(listener.run())
        ...
        task.cancel(); await task
    """

    def __init__(self, redis: Redis, manager: ConnectionManager) -> None:
        self._redis = redis
        self._manager = manager

    async def run(self) -> None:
        """CancelledError 를 받을 때까지 영속 실행.

        구독 중 네트워크 단절 등 예외가 발생하면 지수 백오프로 재시도. 서버
        자체를 죽이지 않고 계속 복구를 시도한다.
        """
        backoff = _BACKOFF_MIN_SEC
        while True:
            try:
                await self._subscribe_and_consume()
                # listen() 이 정상 종료(rare)하면 재연결 시도.
                logger.warning("team_events_listener_exited — reconnecting")
                backoff = _BACKOFF_MIN_SEC
            except asyncio.CancelledError:
                logger.info("team_events_listener_cancelled")
                raise
            except Exception:  # noqa: BLE001
                logger.exception(
                    "team_events_listener_error — retrying in %.1fs", backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, _BACKOFF_MAX_SEC)

    async def _subscribe_and_consume(self) -> None:
        pubsub = self._redis.pubsub()
        try:
            await pubsub.psubscribe(_PATTERN)
            logger.info(
                "team_events_listener_subscribed pattern=%s", _PATTERN
            )
            async for msg in pubsub.listen():
                await self._handle_message(msg)
        finally:
            try:
                await pubsub.punsubscribe(_PATTERN)
                await pubsub.close()
            except Exception:  # noqa: BLE001
                # 정리 실패는 무시 (취소 / 이미 끊긴 상태 등).
                pass

    async def _handle_message(self, msg: dict) -> None:
        # psubscribe 초기 확인(type="psubscribe") 메시지는 무시.
        if msg.get("type") != "pmessage":
            return

        channel = msg.get("channel", "")
        data = msg.get("data", "")
        # decode_responses=True 라 str 로 오지만, 혹시 바이트면 방어적으로 변환.
        if isinstance(channel, bytes):
            channel = channel.decode("utf-8", errors="replace")
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")

        team_id = _parse_team_id(channel)
        if team_id is None:
            logger.warning("team_events_listener_unknown_channel channel=%s", channel)
            return

        try:
            await self._manager.broadcast_to_team(team_id, data)
        except Exception:  # noqa: BLE001
            logger.exception(
                "team_events_listener_broadcast_failed team_id=%s", team_id
            )


def _parse_team_id(channel: str) -> int | None:
    """``team:{id}:events`` → int. 포맷이 다르면 None."""
    parts = channel.split(":")
    if len(parts) != 3 or parts[0] != "team" or parts[2] != "events":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None
