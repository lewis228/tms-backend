# src/audit_log/router.py
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db
from team.dependencies.get_team_scope import get_team_scope

from common.pagination.schemas.pagination_response import CursorPaginationResult
from audit_log.service import AuditLogService
from audit_log.schemas.request import PaginateAuditLogRequest
from audit_log.schemas.response import AuditLogResponseSchema

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("", response_model=CursorPaginationResult[AuditLogResponseSchema])
async def list_audit_logs(
    request: PaginateAuditLogRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """최근 활동 로그(커서 페이징, 필터: entity_type/action)."""
    return await AuditLogService(db, team_id).list_recent(request)


@router.get("/{entity_type}/{entity_id}", response_model=List[AuditLogResponseSchema])
async def list_entity_audit_logs(
    entity_type: str,
    entity_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """특정 엔티티(예: delivery_order/123)의 활동 타임라인."""
    return await AuditLogService(db, team_id).list_for_entity(entity_type, entity_id)
