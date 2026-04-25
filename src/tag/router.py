from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database.dependencies import get_write_db, get_read_db
from auth.dependencies.jwt_or_api_key import jwt_or_api_key, AuthResult
from auth.dependencies.rate_limit import rate_limit
from team.dependencies.get_team_scope import get_team_scope
from user.dependencies.current_user import get_current_user
from user.schemas.response import UserResponseSchema
from tag.schemas.request import CreateTagRequestSchema, UpdateTagRequestSchema
from tag.schemas.response import TagResponseSchema
from tag.service import TagService

router = APIRouter(prefix="/api/v1/tags", tags=["tag"])


@router.get("", response_model=List[TagResponseSchema])
async def list_tags(
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = TagService(db, team_id)
    return await svc.list_tags()


@router.post("", response_model=TagResponseSchema, status_code=201)
async def create_tag(
    body: CreateTagRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = TagService(db, team_id)
    return await svc.create_tag(body, creator_user_id=me.id)


@router.patch("/{tag_id}", response_model=TagResponseSchema)
async def update_tag(
    tag_id: int,
    body: UpdateTagRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = TagService(db, team_id)
    return await svc.update_tag(tag_id, body, updater_user_id=me.id)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    svc = TagService(db, team_id)
    await svc.delete_tag(tag_id)
