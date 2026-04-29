# src/demurrage/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_write_db
from rbac.const.const import DO_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope

from demurrage.service import apply_daily_charges


router = APIRouter(prefix="/api/v1/demurrage", tags=["demurrage"])


@router.post("/run-daily")
async def run_daily(
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """현재 team 의 모든 컨테이너에 대해 demurrage/detention 자동 LegCharge 적용.

    매일 한 번 cron 으로 호출하거나 운영자가 수동 트리거.
    """
    return await apply_daily_charges(db, team_id)
