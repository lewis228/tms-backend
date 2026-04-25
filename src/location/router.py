from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from database.dependencies import get_read_db
from location.schemas.response import LocationResponseSchema
from location.service import LocationService

router = APIRouter(prefix="/api/v1/locations", tags=["location"])


@router.get("", response_model=List[LocationResponseSchema])
async def search_locations(
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    search: Optional[str] = Query(None, max_length=100, description="Free-text search on name / UN/LOCODE / IATA."),
    country_code: Optional[str] = Query(None, max_length=2, description="ISO 3166-1 alpha-2 filter."),
    kind: Optional[str] = Query(None, max_length=20, description="Filter by kind (seaport / airport / ...)."),
    supported_only: bool = Query(True, description="Exclude deprecated / unsupported entries."),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_read_db),
):
    """Search the global location catalogue (UN/LOCODE backed).

    Authenticated — any JWT / API key user. Not team-scoped; locations are
    shared across teams and transport modes.
    """
    _ = auth
    svc = LocationService(db)
    return await svc.search(
        search=search,
        country_code=country_code,
        kind=kind,
        supported_only=supported_only,
        limit=limit,
    )
