# src/notification/model.py
from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Text, Boolean, ForeignKey, DateTime, JSON,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from notification.const.channel import NotificationChannel, NotificationStatus


class NotificationModel(Base, TeamScopedMixin):
    """In-app + 외부 알림 통합. user_id NULL = team-wide broadcast."""
    __tablename__ = "notification"

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=True,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, name="notification_channel"),
        default=NotificationChannel.PUSH, nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus, name="notification_status"),
        default=NotificationStatus.PENDING,
        server_default=NotificationStatus.PENDING.value,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title:      Mapped[str] = mapped_column(String(255), nullable=False)
    body:       Mapped[str | None] = mapped_column(Text, nullable=True)
    payload:    Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    is_read:  Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    read_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_notification_team_id_id"),
        Index("ix_notification_team_user_read", "team_id", "user_id", "is_read"),
        Index("ix_notification_team_status",    "team_id", "status"),
        Index("ix_notification_team_active_id", "team_id", "is_active", "id"),
        Index("ix_notification_team_created_at","team_id", "created_at"),
    )
