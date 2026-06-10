# src/rate_sheet/router.py
from __future__ import annotations
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import RATE_SHEET_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from rate_sheet.service import RateSheetService
from rate_sheet.resolve import RateResolver
from rate_sheet.const.status import RateContainerSize
from rate_sheet.schemas.request import (
    RateSheetCreateRequest, RateSheetUpdateRequest, PaginateRateSheetRequest,
    SetRateEntryRequest, BulkSetRateEntryRequest, RateResolvePreviewRequest,
)
from rate_sheet.schemas.response import (
    RateSheetResponseSchema, RateSheetDetailResponseSchema, RateSheetDeleteResponseSchema,
    RateEntryResponseSchema, RateEntryHistoryResponseSchema, RateLookupResultSchema,
    RateResolveResultSchema,
)

router = APIRouter(prefix="/api/v1/rate-sheets", tags=["rate-sheets"])


# ── 슬롯 CRUD ───────────────────────────────────────────────────
@router.post("", response_model=RateSheetResponseSchema)
async def create_rate_sheet(
    body: RateSheetCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_SHEET_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Sheet(슬롯) 생성 — (group,kind,move_type,service_type) 단위. 쓰기 권한 필요."""
    return await RateSheetService(db, team_id).create_sheet(body, actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[RateSheetResponseSchema])
async def list_rate_sheets(
    request: PaginateRateSheetRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Sheet 목록(슬롯 status/충진 셀 수 포함)."""
    return await RateSheetService(db, team_id).list_sheets(request)


@router.get("/sync", response_model=SyncResponse[RateSheetResponseSchema])
async def sync_rate_sheets(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Sheet Delta Sync."""
    return await RateSheetService(db, team_id).sync_delta(since)


@router.post("/resolve/preview", response_model=RateResolveResultSchema)
async def resolve_rate_preview(
    body: RateResolvePreviewRequest,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """요율 종합 해석 미리보기 — driver→그룹→method 분기로 단가 산출(정산 snapshot 원천)."""
    return await RateResolver(db, team_id).resolve(**body.model_dump())


@router.get("/{sheet_id}", response_model=RateSheetDetailResponseSchema)
async def get_rate_sheet(
    sheet_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Rate Sheet 상세(현재 유효 셀 포함)."""
    return await RateSheetService(db, team_id).get_sheet(sheet_id)


@router.put("/{sheet_id}", response_model=RateSheetResponseSchema)
async def update_rate_sheet(
    sheet_id: int,
    body: RateSheetUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_SHEET_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Sheet 헤더(note) 수정."""
    return await RateSheetService(db, team_id).update_sheet(sheet_id, body, actor_user_id=int(me.id))


@router.delete("/{sheet_id}", response_model=RateSheetDeleteResponseSchema)
async def delete_rate_sheet(
    sheet_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_SHEET_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Rate Sheet 삭제(소프트)."""
    return await RateSheetService(db, team_id).delete_sheet(sheet_id, actor_user_id=int(me.id))


# ── 셀 버전 (set_rate) ──────────────────────────────────────────
@router.post("/{sheet_id}/entries", response_model=RateEntryResponseSchema)
async def set_rate_entry(
    sheet_id: int,
    body: SetRateEntryRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_SHEET_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """셀 요율 등록/변경(유효일자 버전 추가). 기존 버전은 close/supersede 로 보존."""
    return await RateSheetService(db, team_id).set_rate(sheet_id, body, actor_user_id=int(me.id))


@router.post("/{sheet_id}/entries/bulk", response_model=List[RateEntryResponseSchema])
async def set_rate_entries_bulk(
    sheet_id: int,
    body: BulkSetRateEntryRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_SHEET_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """그리드 일괄 저장(여러 셀)."""
    return await RateSheetService(db, team_id).set_rate_bulk(sheet_id, body, actor_user_id=int(me.id))


@router.get("/{sheet_id}/entries", response_model=List[RateEntryResponseSchema])
async def list_rate_entries(
    sheet_id: int,
    as_of: Optional[date] = Query(default=None, description="이 날짜에 유효한 셀들"),
    only_open: bool = Query(default=True, description="as_of 미지정 시 현재 유효(무제한)만"),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """시트의 셀 목록(현재 유효 또는 특정일 기준)."""
    return await RateSheetService(db, team_id).list_entries(sheet_id, as_of=as_of, only_open=only_open)


@router.get("/{sheet_id}/history", response_model=List[RateEntryHistoryResponseSchema])
async def get_rate_sheet_history(
    sheet_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """시트 요율 변경 이력(최근 500건)."""
    return await RateSheetService(db, team_id).get_history(sheet_id)


@router.get("/{sheet_id}/lookup", response_model=RateLookupResultSchema)
async def lookup_rate_entry(
    sheet_id: int,
    work_date: date = Query(..., description="조회 기준일"),
    from_zone_id: Optional[int] = Query(default=None),
    to_zone_id: Optional[int] = Query(default=None),
    from_city: Optional[str] = Query(default=None),
    from_state: Optional[str] = Query(default=None),
    to_city: Optional[str] = Query(default=None),
    to_state: Optional[str] = Query(default=None),
    container_size: Optional[RateContainerSize] = Query(default=None),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """work_date 기준 셀 단가 조회(미등록이면 found=False)."""
    cell = {
        "from_zone_id": from_zone_id, "to_zone_id": to_zone_id,
        "from_city": from_city, "from_state": from_state,
        "to_city": to_city, "to_state": to_state, "container_size": container_size,
    }
    return await RateSheetService(db, team_id).lookup(sheet_id, cell, work_date)
