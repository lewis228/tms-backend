# src/terminal/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Numeric, Text, Index, UniqueConstraint
from decimal import Decimal

from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin


class TerminalModel(Base, TenantScopedMixin):
    """터미널 (Tenant-Scoped)."""
    __tablename__ = "terminal"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_terminal_tenant_id_id"),
        UniqueConstraint("tenant_id", "code", name="uq_terminal_tenant_code"),
        Index("ix_terminal_tenant_active_id", "tenant_id", "is_active", "id"),
        Index("ix_terminal_tenant_name",       "tenant_id", "name"),
        Index("ix_terminal_tenant_updated_at", "tenant_id", "updated_at"),
    )
