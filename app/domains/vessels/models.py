"""Vessel 모델 — 본선."""
from __future__ import annotations

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin


class Vessel(TenantAuditMixin, Base):
    __tablename__ = "vessels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_vessels_tenant_name"),
        Index("ix_vessels_tenant_imo", "tenant_id", "imo_number"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    imo_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    line: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
