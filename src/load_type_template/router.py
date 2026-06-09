# src/load_type_template/router.py
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.tokens.access_token import access_token
from database.dependencies import get_read_db, get_write_db
from rbac.const.const import LOAD_TYPE_TEMPLATE_WRITE
from rbac.dependencies.guards import permission_guard
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema

from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.schemas.sync_response import SyncResponse
from load_type_template.service import LoadTypeTemplateService
from load_type_template.schemas.request import (
    LoadTypeTemplateCreateRequest, LoadTypeTemplateUpdateRequest,
    PaginateLoadTypeTemplateRequest, TemplateStepsReplaceRequest,
)
from load_type_template.schemas.response import (
    LoadTypeTemplateResponseSchema, LoadTypeTemplateSummarySchema,
    LoadTypeTemplateDeleteResponseSchema, SeedDefaultsResponseSchema,
)

router = APIRouter(prefix="/api/v1/load-type-templates", tags=["load-type-templates"])


@router.post("", response_model=LoadTypeTemplateResponseSchema)
async def create_template(
    body: LoadTypeTemplateCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LOAD_TYPE_TEMPLATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """Load Type 템플릿 생성(steps 인라인)."""
    return await LoadTypeTemplateService(db, team_id).create(body, actor_user_id=int(me.id))


@router.post("/seed-defaults", response_model=SeedDefaultsResponseSchema)
async def seed_default_templates(
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LOAD_TYPE_TEMPLATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """컨플루언스 16종 기본 템플릿 시드(이미 있으면 skip)."""
    return await LoadTypeTemplateService(db, team_id).seed_defaults(actor_user_id=int(me.id))


@router.get("", response_model=CursorPaginationResult[LoadTypeTemplateSummarySchema])
async def list_templates(
    request: PaginateLoadTypeTemplateRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Load Type 템플릿 목록."""
    return await LoadTypeTemplateService(db, team_id).list_paginated(request)


@router.get("/sync", response_model=SyncResponse[LoadTypeTemplateSummarySchema])
async def sync_templates(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await LoadTypeTemplateService(db, team_id).sync_delta(since)


@router.get("/{tpl_id}", response_model=LoadTypeTemplateResponseSchema)
async def get_template(
    tpl_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Load Type 템플릿 상세(steps 포함)."""
    return await LoadTypeTemplateService(db, team_id).get(tpl_id)


@router.put("/{tpl_id}", response_model=LoadTypeTemplateResponseSchema)
async def update_template(
    tpl_id: int,
    body: LoadTypeTemplateUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LOAD_TYPE_TEMPLATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """템플릿 헤더 수정."""
    return await LoadTypeTemplateService(db, team_id).update(tpl_id, body, actor_user_id=int(me.id))


@router.put("/{tpl_id}/steps", response_model=LoadTypeTemplateResponseSchema)
async def replace_template_steps(
    tpl_id: int,
    body: TemplateStepsReplaceRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LOAD_TYPE_TEMPLATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """템플릿 steps 전체 교체."""
    return await LoadTypeTemplateService(db, team_id).replace_steps(tpl_id, body, actor_user_id=int(me.id))


@router.delete("/{tpl_id}", response_model=LoadTypeTemplateDeleteResponseSchema)
async def delete_template(
    tpl_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(LOAD_TYPE_TEMPLATE_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    """템플릿 삭제(소프트)."""
    return await LoadTypeTemplateService(db, team_id).delete(tpl_id, actor_user_id=int(me.id))
