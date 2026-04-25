from __future__ import annotations
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from tag.model import TagModel
from tag.repository import TagRepository
from tag.schemas.request import CreateTagRequestSchema, UpdateTagRequestSchema
from tag.schemas.response import TagResponseSchema
from common.exceptions.base import AppException, NotFoundException
from fastapi import status


class TagService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = TagRepository(db, team_id)

    async def list_tags(self) -> List[TagResponseSchema]:
        tags = await self.repo.list_by_team()
        return [TagResponseSchema.model_validate(t) for t in tags]

    async def create_tag(
        self,
        body: CreateTagRequestSchema,
        *,
        creator_user_id: int,
    ) -> TagResponseSchema:
        existing = await self.repo.get_by_name(body.name)
        if existing:
            raise AppException(
                code="TAG_DUPLICATE",
                message="같은 이름의 태그가 이미 존재합니다.",
                status_code=status.HTTP_409_CONFLICT,
            )
        tag = TagModel(
            name=body.name,
            color=body.color,
            created_by_user_id=creator_user_id,
            updated_by_user_id=creator_user_id,
        )
        tag = await self.repo.create(tag)
        return TagResponseSchema.model_validate(tag)

    async def update_tag(
        self,
        tag_id: int,
        body: UpdateTagRequestSchema,
        *,
        updater_user_id: int,
    ) -> TagResponseSchema:
        tag = await self.repo.get_by_id(tag_id)
        if not tag:
            raise NotFoundException("Tag")
        # 팀 소유 검증은 리포의 team_id 필터가 이미 처리한다.

        if body.name is not None and body.name != tag.name:
            collision = await self.repo.get_by_name(body.name)
            if collision and collision.id != tag.id:
                raise AppException(
                    code="TAG_DUPLICATE",
                    message="같은 이름의 태그가 이미 존재합니다.",
                    status_code=status.HTTP_409_CONFLICT,
                )
            tag.name = body.name
        if body.color is not None:
            tag.color = body.color
        tag.updated_by_user_id = updater_user_id
        await self.db.flush()
        await self.db.refresh(tag)
        return TagResponseSchema.model_validate(tag)

    async def delete_tag(self, tag_id: int) -> None:
        """Soft-delete. ocean_shipment_tags 의 조인 row 는 FK RESTRICT 로 하드 삭제
        차단되어 유지된다 — 목록 엔드포인트는 ``is_active`` 로 필터링하므로
        pickers 에서 사라지지만 과거 첨부는 감사 목적상 조회 가능."""
        tag = await self.repo.get_by_id(tag_id)
        if not tag:
            raise NotFoundException("Tag")
        tag.is_active = False
        await self.db.flush()
