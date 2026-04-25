"""WebSocket 연결 레지스트리.

``team_id → Set[WebSocket]`` 매핑만 관리. 단일 uvicorn 프로세스 내에선 메모리로
충분하고, 멀티 프로세스/파드 환경은 Redis Pub/Sub 의 fanout 특성상 각 프로세스가
독립적으로 필요한 이벤트를 수신하므로 이 ConnectionManager 만 있으면 된다.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._by_team: dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, team_id: int, ws: WebSocket) -> None:
        """accept 는 호출부가 이미 수행한 상태로 들어온다 (핸드셰이크 인증 순서 때문)."""
        async with self._lock:
            self._by_team.setdefault(team_id, set()).add(ws)

    async def disconnect(self, team_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._by_team.get(team_id)
            if conns is None:
                return
            conns.discard(ws)
            if not conns:
                self._by_team.pop(team_id, None)

    async def broadcast_to_team(self, team_id: int, message: str) -> None:
        """해당 팀에 접속된 모든 WS 로 text 전송.

        연결이 끊긴 WS 에는 send 가 실패하므로 disconnect 로 정리. lock 밖에서
        send 하기 위해 snapshot 을 먼저 뜬다 (broadcast 중 새 connect 는 다음
        메시지부터 합류, 기존 disconnect 는 여기서 정리)."""
        async with self._lock:
            conns = list(self._by_team.get(team_id, ()))
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "broadcast send failed team_id=%s — pruning connection", team_id
                )
                await self.disconnect(team_id, ws)

    def team_connection_count(self, team_id: int) -> int:
        """운영 관찰용."""
        return len(self._by_team.get(team_id, ()))


# 싱글톤 — 같은 프로세스의 다른 모듈에서 동일 인스턴스를 공유해야 한다.
connection_manager = ConnectionManager()
