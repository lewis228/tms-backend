# src/driver/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, ForeignKey, Index, UniqueConstraint

from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin


class DriverModel(Base, TenantScopedMixin):
    """기사 (Tenant-Scoped). User 와 1:1 — User.role=DRIVER."""
    __tablename__ = "driver"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False,
    )
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_state:  Mapped[str | None] = mapped_column(String(8),  nullable=True)
    truck_number:   Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_driver_tenant_id_id"),
        UniqueConstraint("tenant_id", "user_id", name="uq_driver_tenant_user"),
        UniqueConstraint("tenant_id", "truck_number", name="uq_driver_tenant_truck"),
        Index("ix_driver_tenant_active_id", "tenant_id", "is_active", "id"),
        Index("ix_driver_tenant_user", "tenant_id", "user_id"),
        Index("ix_driver_tenant_updated_at", "tenant_id", "updated_at"),
    )
