# src/location/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Numeric, Text, Index, UniqueConstraint, ForeignKey,
    Enum as SAEnum,
)
from decimal import Decimal

from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin
from location.const.kind import LocationKind


class LocationModel(Base, TenantScopedMixin):
    """장소 (Tenant-Scoped) — 야드/고객사 주소/항만 등."""
    __tablename__ = "location"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[LocationKind] = mapped_column(
        SAEnum(LocationKind, name="location_kind"),
        default=LocationKind.YARD,
        server_default=LocationKind.YARD.value,
        nullable=False,
    )
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_location_tenant_id_id"),
        Index("ix_location_tenant_active_id", "tenant_id", "is_active", "id"),
        Index("ix_location_tenant_kind", "tenant_id", "kind"),
        Index("ix_location_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_location_tenant_name",       "tenant_id", "name"),
        Index("ix_location_tenant_updated_at", "tenant_id", "updated_at"),
    )
