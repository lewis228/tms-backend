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
from common.model.tenant_scoped_mixin import TenantScopedMixin
from notification.const.channel import NotificationChannel, NotificationStatus


class NotificationModel(Base, TenantScopedMixin):
    """In-app + 외부 알림 통합. user_id NULL = tenant-wide broadcast."""
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
        UniqueConstraint("tenant_id", "id", name="uq_notification_tenant_id_id"),
        Index("ix_notification_tenant_user_read", "tenant_id", "user_id", "is_read"),
        Index("ix_notification_tenant_status",    "tenant_id", "status"),
        Index("ix_notification_tenant_active_id", "tenant_id", "is_active", "id"),
        Index("ix_notification_tenant_created_at","tenant_id", "created_at"),
    )
