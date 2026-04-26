# src/notification/fan_out.py
"""RealtimeEvent → Notification inbox fan-out.

호출처: realtime.service.publish(event, *, db=...) 가 자동 호출.
단순 규칙: tenant 의 활성 멤버 (UserTenantModel.is_active=True) 의 user 중
- DRIVER role 제외 (모바일 푸시 별도)
- actor 본인 제외
에게 inbox 행 생성. add + flush only — commit 은 호출처가.
"""
from __future__ import annotations
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notification.const.channel import NotificationChannel, NotificationStatus
from notification.model import NotificationModel
from realtime.schemas.event import RealtimeEvent
from tenant.model import UserTenantModel
from user.const.roles import RolesEnum
from user.model import UserModel


# ── event_type → (title, body 추출 함수) ──────────────────────
_EVENT_TITLES: dict[str, str] = {
    "do.created":           "새 D/O 가 생성되었습니다",
    "do.status_changed":    "D/O 상태가 변경되었습니다",
    "leg.created":          "새 Leg 이 생성되었습니다",
    "leg.status_changed":   "Leg 상태가 변경되었습니다",
    "settlement.calculated":"정산이 계산되었습니다",
    "settlement.adjusted":  "정산이 조정되었습니다",
    "settlement.approved":  "정산이 승인되었습니다",
    "settlement.unapproved":"정산 승인이 취소되었습니다",
}


def _format_body(event: RealtimeEvent) -> str | None:
    p = event.payload or {}
    if event.type in {"do.status_changed", "leg.status_changed"}:
        f, t = p.get("from"), p.get("to")
        if f and t:
            return f"{f} → {t}"
    if event.type in {"do.created", "leg.created"}:
        do_id = p.get("deliveryOrderId")
        if do_id:
            return f"D/O {do_id}"
    if event.type.startswith("settlement."):
        sid = p.get("settlementId")
        if sid:
            return f"Settlement {sid}"
    return None


async def fan_out_event(db: AsyncSession, event: RealtimeEvent) -> int:
    """Notification rows 를 add + flush only. commit 은 호출처."""
    if event.type not in _EVENT_TITLES:
        return 0
    title = _EVENT_TITLES[event.type]
    body = _format_body(event)

    # tenant 의 활성 멤버 user_id 조회 (DRIVER 제외, actor 제외)
    stmt = (
        select(UserModel.id)
        .join(UserTenantModel, UserTenantModel.user_id == UserModel.id)
        .where(
            UserTenantModel.tenant_id == event.tenant_id,
            UserTenantModel.is_active.is_(True),
            UserModel.is_active.is_(True),
            UserModel.role != RolesEnum.DRIVER,
        )
    )
    if event.actor_id:
        stmt = stmt.where(UserModel.id != event.actor_id)
    user_ids = list((await db.execute(stmt)).scalars().all())
    if not user_ids:
        return 0

    payload_dict: dict[str, Any] | None = event.payload
    for uid in user_ids:
        db.add(NotificationModel(
            tenant_id=event.tenant_id,
            user_id=uid,
            channel=NotificationChannel.PUSH,
            status=NotificationStatus.PENDING,
            event_type=event.type,
            title=title,
            body=body,
            payload=payload_dict,
        ))
    await db.flush()
    return len(user_ids)
