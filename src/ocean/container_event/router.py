from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database.dependencies import get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from team.dependencies.get_team_scope import get_team_scope
from ocean.container_event.schemas.response import ContainerEventResponseSchema
from ocean.container_event.service import ContainerEventService

router = APIRouter(prefix="/api/v1/ocean/shipments/{shipment_id}/events", tags=["container_event"])


@router.get("", response_model=List[ContainerEventResponseSchema])
async def list_events(
    shipment_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = ContainerEventService(db, team_id)
    return await svc.list_by_shipment(shipment_id)
