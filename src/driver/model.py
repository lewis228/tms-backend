# src/driver/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, ForeignKey, Index, UniqueConstraint

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class DriverModel(Base, TeamScopedMixin):
    """기사 (Team-Scoped). User 와 1:1 — User.role=DRIVER."""
    __tablename__ = "driver"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False,
    )
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_state:  Mapped[str | None] = mapped_column(String(8),  nullable=True)
    truck_number:   Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_driver_team_id_id"),
        UniqueConstraint("team_id", "user_id", name="uq_driver_team_user"),
        UniqueConstraint("team_id", "truck_number", name="uq_driver_team_truck"),
        Index("ix_driver_team_active_id", "team_id", "is_active", "id"),
        Index("ix_driver_team_user", "team_id", "user_id"),
        Index("ix_driver_team_updated_at", "team_id", "updated_at"),
    )
