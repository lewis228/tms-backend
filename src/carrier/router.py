from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from carrier.schemas.response import CarrierResponseSchema
from carrier.service import CarrierService
from database.dependencies import get_read_db

router = APIRouter(prefix="/api/v1/carriers", tags=["carrier"])


@router.get("", response_model=List[CarrierResponseSchema])
async def list_carriers(
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    supported_only: bool = Query(
        True,
        description="Only return carriers marked is_supported=true (default picker behaviour).",
    ),
    scrapable_only: bool = Query(
        False,
        description="Restrict to carriers that have a scraper_key populated.",
    ),
    search: Optional[str] = Query(
        None,
        max_length=100,
        description="Free-text filter on carrier name or SCAC.",
    ),
    db: AsyncSession = Depends(get_read_db),
):
    """Return the ocean carrier catalogue.

    Authenticated — any user with a valid JWT or API key can read the
    catalogue (it is not sensitive; the list drives the MBL picker). The
    catalogue is NOT team-scoped: carriers are industry-wide.
    """
    _ = auth  # lint — auth is injected to enforce authentication
    svc = CarrierService(db)
    return await svc.list_carriers(
        supported_only=supported_only,
        scrapable_only=scrapable_only,
        search=search,
    )
