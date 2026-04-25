"""Realtime 라우터 — WebSocket.

엔드포인트: `GET /api/v1/ws?token=<JWT>&tenant_id=<id>`
- token 은 access JWT. 만료/무효 시 4001/4002 close.
- tenant_id 쿼리는 SUPER_ADMIN 만 의미 있음 (일반 사용자는 JWT.tenant_id 사용).
- 클라가 send 하는 메시지: `{"type": "ping"}` 만 처리. 그 외 type 은 무시 (envelope 통일).
- 서버가 send 하는 메시지: `{"type": "<event>", "tenantId": ..., "actorId": ..., "payload": {...}, "occurredAt": "..."}`.
- 서버 → 30s ping 자동. 60s 내 pong/메시지 없으면 4004 close (좀비 연결 방지).

Close codes (4xxx 일반):
- 4001 EXPIRED — 토큰 만료
- 4002 INVALID — 토큰 해독 실패 / 잘못된 type / role 없음
- 4003 NO_TENANT — tenant 미해결
- 4004 IDLE_TIMEOUT — pong 없음
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.config import settings
from app.core.logging import get_logger
from app.domains.realtime.service import _Connection, manager

router = APIRouter(tags=["realtime"])

log = get_logger("realtime.ws")

CODE_EXPIRED = 4001
CODE_INVALID = 4002
CODE_NO_TENANT = 4003
CODE_IDLE_TIMEOUT = 4004

PING_INTERVAL_SECONDS = 30
IDLE_TIMEOUT_SECONDS = 60


def _decode(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return {"__error": "expired"}
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


def _resolve_tenant(payload: dict, query_tenant: str | None) -> str | None:
    role = payload.get("role")
    jwt_tenant = payload.get("tenant_id")
    if role == "SUPER_ADMIN":
        return query_tenant or jwt_tenant
    if jwt_tenant and query_tenant and query_tenant != jwt_tenant:
        return None
    return jwt_tenant


@router.websocket("/api/v1/ws")
async def realtime_ws(
    websocket: WebSocket,
    token: str = Query(...),
    tenant_id: str | None = Query(default=None, alias="tenant_id"),
) -> None:
    # WS 4xxx close code 가 클라에 전달되려면 먼저 accept 해야 한다.
    # accept 전에 close 하면 starlette 가 handshake 거부 = HTTP 403 으로 끝내서 4xxx code 가 사라진다.
    await websocket.accept()

    payload = _decode(token)
    if payload is None:
        await websocket.close(code=CODE_INVALID, reason="invalid token")
        return
    if payload.get("__error") == "expired":
        await websocket.close(code=CODE_EXPIRED, reason="token expired")
        return

    user_id = payload.get("sub")
    role = payload.get("role")
    if not user_id or not role:
        await websocket.close(code=CODE_INVALID, reason="bad payload")
        return

    resolved = _resolve_tenant(payload, tenant_id)
    if not resolved:
        await websocket.close(code=CODE_NO_TENANT, reason="tenant required")
        return
    conn = _Connection(websocket, tenant_id=resolved, user_id=user_id)
    await manager.register(conn)

    last_recv_at = time.monotonic()

    async def _send_loop() -> None:
        while True:
            raw = await conn.queue.get()
            await websocket.send_text(raw)

    async def _recv_loop() -> None:
        nonlocal last_recv_at
        while True:
            text = await websocket.receive_text()
            last_recv_at = time.monotonic()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            mtype = msg.get("type")
            if mtype == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            # 그 외 타입은 무시 (envelope 통일, 미래 확장용)

    async def _heartbeat() -> None:
        nonlocal last_recv_at
        while True:
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            if time.monotonic() - last_recv_at > IDLE_TIMEOUT_SECONDS:
                # 좀비 연결 — 강제 종료
                with contextlib.suppress(Exception):
                    await websocket.close(code=CODE_IDLE_TIMEOUT, reason="idle")
                return
            await websocket.send_text(json.dumps({"type": "ping"}))

    send_task = asyncio.create_task(_send_loop(), name="ws-send")
    recv_task = asyncio.create_task(_recv_loop(), name="ws-recv")
    hb_task = asyncio.create_task(_heartbeat(), name="ws-heartbeat")
    tasks = (send_task, recv_task, hb_task)
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            exc = t.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                log.warning("realtime.ws_task_error", task=t.get_name(), error=str(exc))
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        await manager.unregister(conn)
        with contextlib.suppress(Exception):
            await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
