"""Notification 서비스 — 생성/조회/읽음 처리.

발송 자체 (Email/SMS/Push) 는 별도 워커. 본 서비스는 DB 기록만.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.domains.notifications.models import Notification
from app.domains.notifications.repository import NotificationRepository
from app.domains.notifications.schema import NotificationCreateRequest
from app.domains.realtime.schema import RealtimeEvent
from app.domains.users.models import User
from app.models.enums import NotificationChannel, UserRole

# 이벤트 type → (title, body) 매핑. 알 수 없는 type 은 fan-out 대상 아님.
_EVENT_TITLES: dict[str, str] = {
    "do.created": "새 D/O 가 생성되었습니다",
    "do.status_changed": "D/O 상태가 변경되었습니다",
    "leg.created": "새 Leg 이 생성되었습니다",
    "leg.status_changed": "Leg 상태가 변경되었습니다",
    "settlement.calculated": "정산이 계산되었습니다",
    "settlement.adjusted": "정산이 조정되었습니다",
    "settlement.approved": "정산이 승인되었습니다",
    "settlement.unapproved": "정산 승인이 취소되었습니다",
}


def _format_body(event: RealtimeEvent) -> str | None:
    """payload 에서 사람이 읽을 수 있는 보조 텍스트 추출."""
    p = event.payload or {}
    if event.type == "do.status_changed":
        from_ = p.get("from")
        to = p.get("to")
        if from_ and to:
            return f"{from_} → {to}"
    if event.type == "leg.status_changed":
        st = p.get("status")
        if st:
            return f"→ {st}"
    if event.type == "do.created":
        do_id = p.get("deliveryOrderId")
        if do_id:
            return f"D/O {do_id}"
    if event.type == "leg.created":
        do_id = p.get("deliveryOrderId")
        if do_id:
            return f"D/O {do_id}"
    return None


async def fan_out_event(db: AsyncSession, event: RealtimeEvent) -> int:
    """RealtimeEvent 를 tenant 의 web 사용자 inbox 에 fan-out (add + flush only).

    대상:
    - tenant 의 ADMIN + DISPATCHER (active, not deleted)
    - actor 본인 제외 (자기가 한 일을 자기가 알림 받지 않도록)
    - DRIVER 는 모바일 푸시가 별도라 inbox 대상에서 제외
    - SUPER_ADMIN 은 user.tenant_id 가 NULL 이라 자동 제외 (운영자, inbox 대상 아님)

    트랜잭션 책임:
    - 이 함수는 Notification row 를 add + flush 만 한다. **commit 은 호출처가** 한다.
      (기존 도메인 트랜잭션과 분리해서 inbox 만 별도로 commit 하기 위함)
    - 알 수 없는 event type 은 무시 (return 0).
    """
    if event.type not in _EVENT_TITLES:
        return 0
    title = _EVENT_TITLES[event.type]
    body = _format_body(event)

    stmt = select(User.id).where(
        User.tenant_id == event.tenant_id,
        User.role.in_([UserRole.ADMIN, UserRole.DISPATCHER]),
        User.is_deleted.is_(False),
        User.is_active.is_(True),
    )
    if event.actor_id:
        stmt = stmt.where(User.id != event.actor_id)
    user_ids = list((await db.execute(stmt)).scalars().all())

    if not user_ids:
        return 0

    for uid in user_ids:
        db.add(
            Notification(
                tenant_id=event.tenant_id,
                user_id=uid,
                channel=NotificationChannel.PUSH,
                event_type=event.type,
                title=title,
                body=body,
                payload=event.payload,
            )
        )
    await db.flush()
    return len(user_ids)


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
