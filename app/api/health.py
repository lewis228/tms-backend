"""Health check — 인증 불필요. Phase 1에서 DB/Redis 연결 체크 추가."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health() -> dict:
    return {"status": "ok"}
