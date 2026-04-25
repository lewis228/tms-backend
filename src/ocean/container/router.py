from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from common.pagination.schemas.pagination_response import CursorPaginationResult
from database.dependencies import get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from team.dependencies.get_team_scope import get_team_scope
from ocean.container.schemas.request import PaginateContainerRequestSchema
from ocean.container.schemas.response import (
    ContainerListRowResponseSchema,
    ContainerResponseSchema,
)
from ocean.container.service import ContainerService

# Shipment 서브리소스 — 기존 상세 페이지에서 사용. 페이지네이션 없음.
router = APIRouter(prefix="/api/v1/ocean/shipments/{shipment_id}/containers", tags=["container"])

# 팀 전역 containers 리스트 — Terminal49 Containers 페이지용. 페이지네이션 + 필터.
global_router = APIRouter(prefix="/api/v1/ocean/containers", tags=["container"])


@router.get("", response_model=List[ContainerResponseSchema])
async def list_containers(
    shipment_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = ContainerService(db, team_id)
    return await svc.list_by_shipment(shipment_id)


@global_router.get(
    "",
    response_model=CursorPaginationResult[ContainerListRowResponseSchema],
)
async def list_containers_global(
    request: PaginateContainerRequestSchema = Depends(),
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """팀 전역 컨테이너 목록. 번호/MBL 검색, 물리 상태 탭, 사이즈·선사 필터
    지원. 페이지당 기본 20개, `take` 로 조정 가능 (최대 100)."""
    svc = ContainerService(db, team_id)
    return await svc.list_containers_paginated(request)
