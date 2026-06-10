# src/rate_import/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import RATE_SHEET_WRITE, RATE_ZONE_WRITE, RATE_GROUP_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from rate_import.service import RateImportService
from rate_import.schemas.request import CsvImportRequest
from rate_import.schemas.response import CsvImportReport

router = APIRouter(prefix="/api/v1/rate-import", tags=["rate-import"])


@router.post("/sheets/{sheet_id}/entries", response_model=CsvImportReport)
async def import_sheet_entries_csv(
    sheet_id: int,
    body: CsvImportRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_SHEET_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """시트 셀(rate_entry) CSV import. dry_run=true 면 검증만(미적용). 오류 1건이라도 있으면 전체 미적용."""
    return await RateImportService(db, team_id).import_sheet_entries(
        sheet_id, body.csv, body.dry_run, actor_user_id=int(me.id),
    )


@router.get("/sheets/{sheet_id}/entries.csv", response_class=PlainTextResponse)
async def export_sheet_entries_csv(
    sheet_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """시트의 현재 유효 셀을 CSV 로 export."""
    text = await RateImportService(db, team_id).export_sheet_entries(sheet_id)
    return PlainTextResponse(content=text, media_type="text/csv")


@router.post("/groups/{group_id}/entries", response_model=CsvImportReport)
async def import_group_entries_csv(
    group_id: int,
    body: CsvImportRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_GROUP_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """그룹 단위 플랫 행(move/service 포함) CSV import. dry_run 지원, 오류 1건이라도 전체 미적용."""
    return await RateImportService(db, team_id).import_group_entries(
        group_id, body.csv, body.dry_run, actor_user_id=int(me.id),
    )


@router.get("/groups/{group_id}/entries.csv", response_class=PlainTextResponse)
async def export_group_entries_csv(
    group_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """그룹의 현재 유효 셀을 플랫 행 CSV 로 export."""
    text = await RateImportService(db, team_id).export_group_entries(group_id)
    return PlainTextResponse(content=text, media_type="text/csv")


@router.post("/zones/{zone_id}/members", response_model=CsvImportReport)
async def import_zone_members_csv(
    zone_id: int,
    body: CsvImportRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(RATE_ZONE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Zone 멤버(zip/city) CSV import(전체 교체). dry_run 지원."""
    return await RateImportService(db, team_id).import_zone_members(
        zone_id, body.csv, body.dry_run, actor_user_id=int(me.id),
    )


@router.get("/zones/{zone_id}/members.csv", response_class=PlainTextResponse)
async def export_zone_members_csv(
    zone_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Zone 멤버를 CSV 로 export."""
    text = await RateImportService(db, team_id).export_zone_members(zone_id)
    return PlainTextResponse(content=text, media_type="text/csv")
