from __future__ import annotations
from typing import List, Optional
from sqlalchemy import select, delete, update, func
from sqlalchemy.orm import selectinload, load_only, with_loader_criteria
from sqlalchemy.ext.asyncio import AsyncSession
from common.pagination.schemas.pagination_response import CursorPaginationResult
from common.pagination.service import CommonService
from team.model import TeamModel, UserTeamModel
from user.model import UserModel
from user.schemas.request import PaginateUserRequestSchema
from auth.const.providers import AuthProviderEnum
from file.model import FileAssetModel


def _norm(email: str) -> str:
    return (email or "").strip().lower()


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.common = CommonService()

    def _with_options_detail(self, stmt):
        return stmt.options(
            load_only(
                UserModel.id, UserModel.email, UserModel.role, UserModel.name,
                UserModel.phone, UserModel.auth_provider, UserModel.oauth_id,
                UserModel.notification_email, UserModel.event_notification_enabled, UserModel.language,
            ),
            selectinload(UserModel.teams).options(
                load_only(UserTeamModel.id, UserTeamModel.team_id, UserTeamModel.permission_group_id),
                selectinload(UserTeamModel.team).options(load_only(TeamModel.id, TeamModel.name)),
            ),
            selectinload(UserModel.files).options(
                load_only(
                    FileAssetModel.id, FileAssetModel.domain, FileAssetModel.object_id,
                    FileAssetModel.subdir, FileAssetModel.filename, FileAssetModel.size,
                    FileAssetModel.mime, FileAssetModel.is_public, FileAssetModel.logical_path,
                )
            ),
            with_loader_criteria(UserTeamModel, UserTeamModel.is_active.is_(True), include_aliases=True),
            with_loader_criteria(FileAssetModel, FileAssetModel.is_active.is_(True), include_aliases=True),
        )

    async def get_user_for_auth(self, email: str) -> Optional[UserModel]:
        stmt = (
            select(UserModel).where(
                UserModel.email == _norm(email),
                UserModel.auth_provider == AuthProviderEnum.EMAIL.value,
                UserModel.is_active.is_(True),
            ).options(load_only(
                UserModel.id, UserModel.email, UserModel.password, UserModel.role,
                UserModel.name, UserModel.phone, UserModel.auth_provider, UserModel.oauth_id,
                UserModel.notification_email, UserModel.event_notification_enabled,
                UserModel.created_at, UserModel.updated_at, UserModel.is_active,
            ))
        )
        return await self.db.scalar(stmt)

    async def get_user_by_oauth(self, provider: AuthProviderEnum, oauth_id: str) -> Optional[UserModel]:
        stmt = select(UserModel).where(
            UserModel.auth_provider == provider.value,
            UserModel.oauth_id == oauth_id,
            UserModel.is_active.is_(True),
        )
        stmt = self._with_options_detail(stmt)
        return await self.db.scalar(stmt)

    async def get_active_user_by_email(self, email: str) -> Optional[UserModel]:
        stmt = select(UserModel).where(
            UserModel.email == _norm(email), UserModel.is_active.is_(True),
        ).options(load_only(UserModel.id, UserModel.email, UserModel.auth_provider))
        return await self.db.scalar(stmt)

    async def check_email_conflict(self, email: str, current_provider: AuthProviderEnum) -> Optional[str]:
        if not email:
            return None
        existing = await self.get_active_user_by_email(email)
        if existing and existing.auth_provider != current_provider.value:
            provider_name = AuthProviderEnum(existing.auth_provider).display_name_ko()
            return f"Email already registered with {provider_name}."
        return None

    async def exists_oauth_user(self, provider: AuthProviderEnum, oauth_id: str) -> bool:
        stmt = select(func.count(UserModel.id)).where(
            UserModel.auth_provider == provider.value, UserModel.oauth_id == oauth_id, UserModel.is_active.is_(True),
        )
        return (await self.db.execute(stmt)).scalar_one() > 0

    async def list_paginated(self, request: PaginateUserRequestSchema) -> CursorPaginationResult[UserModel]:
        base = select(UserModel).where(UserModel.is_active.is_(True))
        base = self._with_options_detail(base)
        if request.where__email__i_like:
            q = f"%{request.where__email__i_like.strip().lower()}%"
            base = base.where(func.lower(UserModel.email).like(q))
        return await self.common.paginate(request=request, model=UserModel, session=self.db, base_query=base, path="user")

    async def get_user_by_id(self, id: int) -> Optional[UserModel]:
        stmt = select(UserModel).where(UserModel.id == id, UserModel.is_active.is_(True))
        stmt = self._with_options_detail(stmt)
        return await self.db.scalar(stmt)

    async def get_user_by_email(self, email: str) -> Optional[UserModel]:
        stmt = select(UserModel).where(UserModel.email == _norm(email), UserModel.is_active.is_(True))
        stmt = self._with_options_detail(stmt)
        return await self.db.scalar(stmt)

    async def has_active_email_conflict(self, email: str, exclude_user_id: Optional[int] = None) -> bool:
        stmt = select(func.count(UserModel.id)).where(UserModel.email == _norm(email), UserModel.is_active.is_(True))
        if exclude_user_id:
            stmt = stmt.where(UserModel.id != exclude_user_id)
        return (await self.db.execute(stmt)).scalar_one() > 0

    async def exists_email(self, email: str) -> bool:
        return await self.has_active_email_conflict(email)

    async def create_user(self, new_user: UserModel) -> UserModel:
        self.db.add(new_user)
        await self.db.flush()
        await self.db.refresh(new_user)
        return new_user

    async def soft_deactivate_user_by_id(self, id: int) -> None:
        await self.db.execute(update(UserModel).where(UserModel.id == id, UserModel.is_active.is_(True)).values(is_active=False))

    async def get_user_team_ids(self, user_id: int) -> List[int]:
        stmt = select(UserTeamModel.team_id).where(UserTeamModel.user_id == user_id)
        rows = (await self.db.execute(stmt)).all()
        return [row[0] for row in rows]

    async def deactivate_memberships_by_user(self, user_id: int) -> None:
        await self.db.execute(update(UserTeamModel).where(UserTeamModel.user_id == user_id, UserTeamModel.is_active.is_(True)).values(is_active=False))

    async def update_password_by_id(self, user_id: int, password_hash: str) -> None:
        await self.db.execute(update(UserModel).where(UserModel.id == user_id).values(password=password_hash))
