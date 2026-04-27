# src/location_ping/model.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Numeric, DateTime, ForeignKey, Index, UniqueConstraint,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class LocationPingModel(Base, TeamScopedMixin):
    """Driver mobile 의 GPS 핑 — 15분 간격 batch insert."""
    __tablename__ = "location_ping"

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("driver.id", ondelete="CASCADE"), nullable=False,
    )
    latitude:  Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    speed_kmh:    Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    heading_deg:  Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    accuracy_m:   Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_location_ping_team_id_id"),
        Index("ix_location_ping_team_driver_time",
              "team_id", "driver_id", "occurred_at"),
        Index("ix_location_ping_team_active_id",
              "team_id", "is_active", "id"),
    )
