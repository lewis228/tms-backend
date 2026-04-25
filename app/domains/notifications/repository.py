"""Notification Repository."""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.pagination import PageParams
from app.core.repository import BaseRepository
from app.domains.notifications.models import Notification


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_for_user(
        self, user_id: str, params: PageParams, *, unread_only: bool = False
    ) -> tuple[list[Notification], int]:
        base = self._base_query().where(Notification.user_id == user_id)
        if unread_only:
            base = base.where(Notification.is_read.is_(False))
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        stmt = (
            base.order_by(Notification.created_at.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        return rows, total

    async def count_unread(self, user_id: str) -> int:
        base = self._base_query().where(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        )
        return (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
