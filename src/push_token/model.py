# src/push_token/model.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, DateTime, ForeignKey, Index, UniqueConstraint,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class PushTokenModel(Base, TeamScopedMixin):
    """FCM / APNs push 토큰. 같은 driver+platform 의 동일 token 은 1 행."""
    __tablename__ = "push_token"

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("driver.id", ondelete="CASCADE"), nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(16), nullable=False)   # fcm / apns
    token:    Mapped[str] = mapped_column(String(512), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_push_token_team_id_id"),
        UniqueConstraint("driver_id", "platform", "token",
                          name="uq_push_token_driver_platform_token"),
        Index("ix_push_token_team_driver", "team_id", "driver_id"),
        Index("ix_push_token_team_active_id", "team_id", "is_active", "id"),
    )
