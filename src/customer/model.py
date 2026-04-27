# src/customer/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Index, UniqueConstraint

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class CustomerModel(Base, TeamScopedMixin):
    """고객사 (Team-Scoped)."""
    __tablename__ = "customer"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    billing_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name:    Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_email:   Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_phone:   Mapped[str | None] = mapped_column(String(64),  nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_customer_team_id_id"),
        UniqueConstraint("team_id", "code", name="uq_customer_team_code"),
        Index("ix_customer_team_active_id", "team_id", "is_active", "id"),
        Index("ix_customer_team_name",       "team_id", "name"),
        Index("ix_customer_team_updated_at", "team_id", "updated_at"),
    )
