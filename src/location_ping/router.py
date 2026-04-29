# src/location_ping/router.py
"""Driver location ping read endpoints (디스패처용).

driver-mobile 은 BATCH POST 만 받지만, 디스패처 화면에서 실시간 위치를 보려면
read 엔드포인트가 필요. team_scope 안에서만 조회.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from common.schemas.base import ResponseSchema
from database.dependencies import get_read_db
from team.dependencies.get_team_scope import get_team_scope
from location_ping.model import LocationPingModel


router = APIRouter(prefix="/api/v1/location-pings", tags=["location-pings"])


class LocationPingResponse(ResponseSchema):
    id: int
    driver_id: int
    latitude: float
    longitude: float
    speed_kmh: float | None = None
    heading_deg: float | None = None
    accuracy_m: float | None = None
    occurred_at: datetime


@router.get("/latest/{driver_id}", response_model=Optional[LocationPingResponse])
async def get_latest_ping(
    driver_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """driver 의 가장 최근 ping 1건. 없으면 null."""
    q = (
        select(LocationPingModel)
        .where(
            LocationPingModel.team_id == team_id,
            LocationPingModel.driver_id == driver_id,
            LocationPingModel.is_active.is_(True),
        )
        .order_by(LocationPingModel.occurred_at.desc())
        .limit(1)
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if row is None:
        return None
    return LocationPingResponse(
        id=row.id,
        driver_id=row.driver_id,
        latitude=float(row.latitude),
        longitude=float(row.longitude),
        speed_kmh=float(row.speed_kmh) if row.speed_kmh is not None else None,
        heading_deg=float(row.heading_deg) if row.heading_deg is not None else None,
        accuracy_m=float(row.accuracy_m) if row.accuracy_m is not None else None,
        occurred_at=row.occurred_at,
    )
