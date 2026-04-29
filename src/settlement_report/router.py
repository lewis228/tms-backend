# src/settlement_report/router.py
from __future__ import annotations
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db
from team.dependencies.get_team_scope import get_team_scope

from settlement_report.service import driver_settlement_report


router = APIRouter(prefix="/api/v1/settlement-reports", tags=["settlement-reports"])


@router.get("/driver/{driver_id}")
async def get_driver_report(
    driver_id: int,
    completed_from: datetime = Query(...),
    completed_to: datetime = Query(...),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
) -> dict[str, Any]:
    """driver 정산서 (v3 LegRate + LegCharge 합산)."""
    return await driver_settlement_report(
        db, team_id,
        driver_id=driver_id,
        completed_from=completed_from,
        completed_to=completed_to,
    )
