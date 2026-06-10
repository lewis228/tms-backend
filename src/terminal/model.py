# src/terminal/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Numeric, Text, Index, UniqueConstraint, ForeignKey
from decimal import Decimal

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class TerminalModel(Base, TeamScopedMixin):
    """터미널 (Team-Scoped)."""
    __tablename__ = "terminal"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    zip_id: Mapped[int | None] = mapped_column(
        ForeignKey("zip_code.id", ondelete="SET NULL"), nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_terminal_team_id_id"),
        UniqueConstraint("team_id", "code", name="uq_terminal_team_code"),
        Index("ix_terminal_team_active_id", "team_id", "is_active", "id"),
        Index("ix_terminal_team_name",       "team_id", "name"),
        Index("ix_terminal_team_updated_at", "team_id", "updated_at"),
        Index("ix_terminal_team_zip", "team_id", "zip_id"),
    )
