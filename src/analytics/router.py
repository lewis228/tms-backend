# src/analytics/router.py
"""H-9 Dashboard analytics endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db
from team.dependencies.get_team_scope import get_team_scope

from analytics.service import AnalyticsService
from analytics.schemas.response import (
    MarginTrendResponse, DriverUtilizationResponse,
    ContainerTurnoverResponse, StreetTurnSavingsResponse,
    ExpiringComplianceResponse,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/expiring-compliance", response_model=ExpiringComplianceResponse)
async def expiring_compliance(
    days: int = Query(30, ge=1, le=365),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """장비/DQ 만료 임박·만료 항목 (truck/chassis/driver, 기본 30일)."""
    return await AnalyticsService(db, team_id).expiring_compliance(days)


@router.get("/margin-trend", response_model=MarginTrendResponse)
async def margin_trend(
    days: int = Query(30, ge=1, le=90),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """일자별 매출 / 지급 / 마진 (최근 N 일, 기본 30일)."""
    return await AnalyticsService(db, team_id).margin_trend(days)


@router.get("/driver-utilization", response_model=DriverUtilizationResponse)
async def driver_utilization(
    days: int = Query(7, ge=1, le=30),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """기사별 가동률 (completed / total) 최근 N 일."""
    return await AnalyticsService(db, team_id).driver_utilization(days)


@router.get("/container-turnover", response_model=ContainerTurnoverResponse)
async def container_turnover(
    days: int = Query(30, ge=1, le=90),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """컨테이너 lifecycle 이벤트 일자별 + 평균 보유일수."""
    return await AnalyticsService(db, team_id).container_turnover(days)


@router.get("/street-turn-savings", response_model=StreetTurnSavingsResponse)
async def street_turn_savings(
    days: int = Query(30, ge=1, le=365),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Street turn 상태별 카운트 + 누적 절감액."""
    return await AnalyticsService(db, team_id).street_turn_savings(days)
