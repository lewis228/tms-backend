"""Realtime 라우터 — SSE.

GET /api/v1/realtime/events  → text/event-stream
인증 필요. 채널은 tenant 별 격리.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.dependencies import CurrentUser, TenantID
from app.domains.realtime.service import subscribe_stream

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])


@router.get("/events")
async def stream_events(_user: CurrentUser, tenant_id: TenantID):
    async def _gen():
        # 초기 ping
        yield ": ping\n\n"
        try:
            async for raw in subscribe_stream(tenant_id):
                yield f"data: {raw}\n\n"
        except asyncio.CancelledError:
            return

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)
