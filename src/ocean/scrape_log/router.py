from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database.dependencies import get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from team.dependencies.get_team_scope import get_team_scope
from ocean.scrape_log.schemas.response import ScrapeLogResponseSchema
from ocean.scrape_log.service import ScrapeLogService

router = APIRouter(prefix="/api/v1/ocean/shipments/{shipment_id}/scrape-logs", tags=["scrape_log"])


@router.get("", response_model=List[ScrapeLogResponseSchema])
async def list_scrape_logs(
    shipment_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = ScrapeLogService(db, team_id)
    return await svc.list_by_shipment(shipment_id)
