"""User Repository — email 글로벌 unique. tenant_id nullable."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.domains.users.models import User


class UserRepository:
    def __init__(self, db: AsyncSession, *, tenant_id: str | None = None) -> None:
        self.db = db
        self.tenant_id = tenant_id

    def _scope(self, stmt):
        stmt = stmt.where(User.is_deleted.is_(False))
        if self.tenant_id is not None:
            stmt = stmt.where(User.tenant_id == self.tenant_id)
        return stmt

    async def get(self, user_id: str) -> User | None:
        stmt = self._scope(select(User).where(User.id == user_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.is_deleted.is_(False))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_paged(self, params: PageParams) -> tuple[list[User], int]:
        base = self._scope(select(User))
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        stmt = base.order_by(User.created_at.desc()).offset(params.offset).limit(params.limit)
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, total

    async def add(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def soft_delete(self, user: User) -> None:
        user.is_deleted = True
        await self.db.flush()
