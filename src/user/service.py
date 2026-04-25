from __future__ import annotations
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from common.pagination.schemas.pagination_response import CursorPaginationResult
from team.model import UserTeamModel
from user.repository import UserRepository
from user.model import UserModel
from user.schemas.request import PaginateUserRequestSchema
from user.schemas.response import UserListItemResponseSchema, UserDetailResponseSchema, UserDeleteResponseSchema
from common.exceptions.base import NotFoundException, ConflictException
from file.service import FileService
from file.const.domains import FileDomain


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)
        self.file_svc = FileService(db)

    async def list_users_paginated(self, request: PaginateUserRequestSchema) -> CursorPaginationResult[UserListItemResponseSchema]:
        result = await self.repo.list_paginated(request)
        items = []
        for r in result.data:
            item = UserListItemResponseSchema.model_validate(r)
            self.file_svc.inject_file_urls(item.files)
            items.append(item)
        result.data = items
        return result

    async def get_user_by_id(self, user_id: int) -> UserDetailResponseSchema:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundException("User")
        response = UserDetailResponseSchema.model_validate(user)
        self.file_svc.inject_file_urls(response.files)
        return response

    async def update_user_profile(
        self, *, user_id: int, name: Optional[str] = None, phone: Optional[str] = None,
        event_notification_enabled: Optional[bool] = None, language: Optional[str] = None,
        temp_keys: List[str] = None, remove_file_ids: List[int] = None,
    ) -> UserDetailResponseSchema:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundException("User")
        if name is not None:
            user.name = name.strip() if name else None
        if phone is not None:
            user.phone = phone.strip() if phone else None
        if event_notification_enabled is not None:
            user.event_notification_enabled = event_notification_enabled
        if language is not None:
            user.language = language.strip() if language else "auto"
        await self.db.flush()
        if temp_keys or remove_file_ids:
            await self.file_svc.commit(
                team_id=None, domain=FileDomain.USER, object_id=user_id,
                subdir="profile", add_temp_keys=temp_keys or [],
                remove_file_ids=remove_file_ids or [], actor_user_id=user_id, is_public=False,
            )
        await self.db.refresh(user)
        user = await self.repo.get_user_by_id(user_id)
        response = UserDetailResponseSchema.model_validate(user)
        self.file_svc.inject_file_urls(response.files)
        return response

    async def delete_user_by_actor(self, *, target_user_id: int) -> UserDeleteResponseSchema:
        user = await self.repo.get_user_by_id(target_user_id)
        if not user:
            raise NotFoundException("User")
        await self.file_svc.soft_deactivate_by_object(team_id=None, domain=FileDomain.USER, object_id=target_user_id, actor_user_id=target_user_id)
        await self.repo.soft_deactivate_user_by_id(target_user_id)
        await self.repo.deactivate_memberships_by_user(target_user_id)
        return UserDeleteResponseSchema(id=target_user_id, deleted=True, soft_deleted=True)
