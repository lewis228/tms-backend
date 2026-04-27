# src/vessel/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Index, UniqueConstraint

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class VesselModel(Base, TeamScopedMixin):
    """본선 (Team-Scoped)."""
    __tablename__ = "vessel"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    imo_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_vessel_team_id_id"),
        UniqueConstraint("team_id", "imo_number", name="uq_vessel_team_imo"),
        Index("ix_vessel_team_active_id", "team_id", "is_active", "id"),
        Index("ix_vessel_team_name",       "team_id", "name"),
        Index("ix_vessel_team_updated_at", "team_id", "updated_at"),
    )
