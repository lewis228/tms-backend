"""Notification 서비스 — 생성/조회/읽음 처리.

발송 자체 (Email/SMS/Push) 는 별도 워커. 본 서비스는 DB 기록만.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import ForbiddenError, NotFoundError
from app.domains.notifications.models import Notification
from app.domains.notifications.repository import NotificationRepository
from app.domains.notifications.schema import NotificationCreateRequest


class NotificationService:
    def __init__(self, repo: NotificationRepository, tenant_id: str) -> None:
        self.repo = repo
        self.tenant_id = tenant_id

    async def create(self, payload: NotificationCreateRequest) -> Notification:
        n = Notification(tenant_id=self.tenant_id, **payload.model_dump())
        await self.repo.create(n)
        await self.repo.db.commit()
        await self.repo.db.refresh(n)
        return n

    async def list_for_user(self, user_id: str, params, *, unread_only: bool = False):
        return await self.repo.list_for_user(user_id, params, unread_only=unread_only)

    async def count_unread(self, user_id: str) -> int:
        return await self.repo.count_unread(user_id)

    async def mark_read(self, id_: str, user_id: str) -> Notification:
        n = await self.repo.get_by_id(id_)
        if not n:
            raise NotFoundError("Notification not found")
        if n.user_id != user_id:
            raise ForbiddenError("Cannot read another user's notification")
        if not n.is_read:
            n.is_read = True
            n.read_at = datetime.now(timezone.utc)
            await self.repo.db.flush()
            await self.repo.db.commit()
            await self.repo.db.refresh(n)
        return n

    async def mark_all_read(self, user_id: str) -> int:
        # 단순 구현: 전체 fetch 후 갱신. 양 많아지면 UPDATE 한 방으로 변경.
        from app.core.pagination import PageParams

        items, _ = await self.repo.list_for_user(
            user_id, PageParams(page=1, size=100), unread_only=True
        )
        now = datetime.now(timezone.utc)
        for n in items:
            n.is_read = True
            n.read_at = now
        await self.repo.db.flush()
        await self.repo.db.commit()
        return len(items)
