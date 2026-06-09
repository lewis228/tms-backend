# src/notification/fan_out.py
"""RealtimeEvent → Notification inbox fan-out.

호출처: realtime.service.publish(event, *, db=...) 가 자동 호출.
단순 규칙: team 의 활성 멤버 (UserTeamModel.is_active=True) 의 user 중
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
from team.model import UserTeamModel
from user.const.roles import RolesEnum
from user.model import UserModel


# ── event_type → (title, body 추출 함수) ──────────────────────
_EVENT_TITLES: dict[str, str] = {
    "do.created":           "새 D/O 가 생성되었습니다",
    "do.status_changed":    "D/O 상태가 변경되었습니다",
    "leg.created":          "새 Leg 이 생성되었습니다",
    "leg.status_changed":   "Leg 상태가 변경되었습니다",
    # 재설계: 구 settlement 도메인 제거 → settlement.* 알림 제거(정산은 payroll 도메인).
    # v3: 컨테이너가 WAITING_PLAN 으로 진입할 때만 디스패처에게 inbox 알림 (next-stop 미생성).
    "container.waiting_plan": "⚠️ 컨테이너 다음 stop 미생성",
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
    if event.type == "container.waiting_plan":
        cid = p.get("containerId")
        if cid:
            return f"Container #{cid} — 다음 stop 을 추가하세요"
    return None


async def fan_out_event(db: AsyncSession, event: RealtimeEvent) -> int:
    """Notification rows 를 add + flush only. commit 은 호출처."""
    if event.type not in _EVENT_TITLES:
        return 0
    title = _EVENT_TITLES[event.type]
    body = _format_body(event)

    # team 의 활성 멤버 user_id 조회 (DRIVER 제외, actor 제외)
    stmt = (
        select(UserModel.id)
        .join(UserTeamModel, UserTeamModel.user_id == UserModel.id)
        .where(
            UserTeamModel.team_id == event.team_id,
            UserTeamModel.is_active.is_(True),
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
            team_id=event.team_id,
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
