"""``/ws`` 엔드포인트 — 팀 scoped 이벤트를 클라이언트로 push.

인증:
  쿼리 파라미터 ``token`` (JWT access) + ``team_id`` 를 핸드셰이크 직후 검증.
  JWT 가 유효하고 유저가 해당 팀 멤버면 연결 허용. 실패면 1008 로 종료.

아키텍처:
  각 WS 연결은 ``ConnectionManager`` 에 등록만 한다. Redis 구독은 **프로세스당
  1개** 인 ``TeamEventsListener`` (``common/events/listener.py``) 가 lifespan
  startup 에서 기동되어 전담한다. 리스너가 ``team:*:events`` 패턴을 수신해
  팀 별로 ``ConnectionManager.broadcast_to_team`` 으로 디스패치.

  이전 구조: WS 연결 1개당 Redis subscribe 1개 → 구독자 수 = 유저 수
  현재 구조: 파드당 Redis subscribe 1개 → 구독자 수 = 파드 수 (오토스케일 친화)

메시지 방향:
  서버 → 클라이언트 단방향 push. 클라이언트 메시지는 수신 루프가 소비만
  하며(disconnect 감지용) 내용은 무시. 향후 채팅/클라이언트 측 액션 추가 시
  여기서 타입 분기.
"""

from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from database.mysql_connection import read_session_maker
from common.const.settings import settings
from team.model import UserTeamModel

from common.events.connection_manager import connection_manager


JWT_ALGORITHM = "HS256"

logger = logging.getLogger(__name__)

ws_router = APIRouter(prefix="/api/v1")


async def _authenticate(
    ws: WebSocket,
    token: str,
    team_id: int,
) -> Optional[int]:
    """JWT 검증 + 팀 멤버십 확인. 성공하면 user_id, 실패하면 None.

    WS 핸드셰이크는 HTTP 와 달리 FastAPI Depends 를 쓰기 어려워서 직접 verify.
    순수 decode + 단일 멤버십 SELECT 로 가볍게 처리한다.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (ExpiredSignatureError, InvalidTokenError):
        logger.debug("ws auth: token decode failed")
        return None
    except Exception:  # noqa: BLE001
        logger.debug("ws auth: unexpected error during decode")
        return None

    if payload.get("type") != "access":
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        return None

    # 팀 멤버십 확인 — 짧게 read DB 세션 열고 닫음.
    try:
        async with read_session_maker() as session:
            session: AsyncSession  # type: ignore[no-redef]
            row = await session.scalar(
                select(UserTeamModel.id)
                .where(
                    UserTeamModel.user_id == user_id,
                    UserTeamModel.team_id == team_id,
                    UserTeamModel.is_active.is_(True),
                )
                .limit(1)
            )
            if row is None:
                return None
    except Exception:  # noqa: BLE001
        logger.exception("ws auth: membership check failed")
        return None

    return user_id


@ws_router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str, team_id: int):
    """단일 WS 엔드포인트. shipment / (향후) 채팅 / 알림 이벤트를 한 연결로 전달.

    쿼리: ``/ws?token=<jwt>&team_id=<int>``.
    """
    # accept 전에 인증 — 실패면 policy violation 으로 close.
    user_id = await _authenticate(ws, token, team_id)
    if user_id is None:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws.accept()
    await connection_manager.connect(team_id, ws)
    logger.info(
        "ws connected user_id=%s team_id=%s total=%d",
        user_id, team_id, connection_manager.team_connection_count(team_id),
    )
    try:
        # 클라이언트 → 서버 메시지를 소비하면서 disconnect 를 감지. 현재 단계에선
        # shipment 이벤트 단방향 push 만 지원하므로 내용은 무시. 채팅 단계에서
        # 이 루프가 메시지 타입 분기 진입점이 된다.
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.debug("ws receive loop exception team_id=%s", team_id)
    finally:
        await connection_manager.disconnect(team_id, ws)
        logger.info(
            "ws disconnected user_id=%s team_id=%s remaining=%d",
            user_id, team_id, connection_manager.team_connection_count(team_id),
        )
