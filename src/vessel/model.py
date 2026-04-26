# src/vessel/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Index, UniqueConstraint

from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin


class VesselModel(Base, TenantScopedMixin):
    """본선 (Tenant-Scoped)."""
    __tablename__ = "vessel"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    imo_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_vessel_tenant_id_id"),
        UniqueConstraint("tenant_id", "imo_number", name="uq_vessel_tenant_imo"),
        Index("ix_vessel_tenant_active_id", "tenant_id", "is_active", "id"),
        Index("ix_vessel_tenant_name",       "tenant_id", "name"),
        Index("ix_vessel_tenant_updated_at", "tenant_id", "updated_at"),
    )
