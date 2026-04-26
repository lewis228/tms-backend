# src/realtime/router.py
"""WebSocket endpoint — token 인증 + tenant 결정 + ping/pong."""
from __future__ import annotations
import asyncio
import json
import structlog
from fastapi import APIRouter, Query, WebSocket, status

from realtime.service import _Connection, manager

router = APIRouter(prefix="/api/v1/ws", tags=["realtime"])

log = structlog.get_logger(__name__)

PING_INTERVAL = 30  # 서버 ping 간격
IDLE_TIMEOUT = 60   # 클라 메시지 없으면 종료 (4004)


@router.websocket("")
async def realtime_ws(
    websocket: WebSocket,
    token: str = Query(...),
    tenant_id: int | None = Query(None, alias="tenant_id"),
):
    """
    /api/v1/ws?token=<JWT>&tenant_id=<id>

    Close codes:
    - 4001: token expired
    - 4002: token invalid / role 없음
    - 4003: tenant 미해결 (SUPER_ADMIN 인데 tenant_id 미지정 등)
    - 4004: ping idle timeout
    """
    # 토큰 디코드 (auth 모듈 활용 — 단순화: 추후 정교 구현)
    try:
        from auth.tokens.access_token import decode_access_token
        claims = decode_access_token(token)
    except Exception:
        await websocket.accept()
        await websocket.close(code=4002)
        return

    user_id = int(claims.get("sub", 0))
    role = claims.get("role")
    claim_tenant = claims.get("tenant_id")

    # tenant 결정
    if role == "SUPER_ADMIN":
        if tenant_id is None:
            await websocket.accept()
            await websocket.close(code=4003)
            return
    else:
        # 일반 유저 — JWT 의 tenant_id 사용. query 와 다르면 거부.
        if claim_tenant is None:
            await websocket.accept()
            await websocket.close(code=4003)
            return
        if tenant_id is not None and int(tenant_id) != int(claim_tenant):
            await websocket.accept()
            await websocket.close(code=4003)
            return
        tenant_id = int(claim_tenant)

    await websocket.accept()
    conn = _Connection(websocket, int(tenant_id), user_id)
    await manager.register(conn)

    async def send_loop():
        try:
            while True:
                raw = await conn.queue.get()
                await websocket.send_text(raw)
        except Exception:
            pass

    send_task = asyncio.create_task(send_loop())

    try:
        # idle timeout 으로 클라 메시지 receive (서버 ping 도 보냄)
        last_ping = asyncio.get_event_loop().time()
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=PING_INTERVAL)
                # 클라 ping 처리
                with __import__("contextlib").suppress(Exception):
                    msg = json.loads(raw)
                    if isinstance(msg, dict) and msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                last_ping = asyncio.get_event_loop().time()
            except asyncio.TimeoutError:
                # 서버 ping
                await websocket.send_text(json.dumps({"type": "ping"}))
                if asyncio.get_event_loop().time() - last_ping > IDLE_TIMEOUT:
                    await websocket.close(code=4004)
                    break
    except Exception:
        pass
    finally:
        send_task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await send_task
        await manager.unregister(conn)
