"""Location 모델 — Yard / Customer 주소 / Port / Other.

LegPickup/Delivery 와 D/O delivery_location/return_location 이 모두 참조.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin
from app.models.enums import LocationKind


class Location(TenantAuditMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        Index("ix_locations_tenant_kind", "tenant_id", "kind"),
        Index("ix_locations_tenant_customer", "tenant_id", "customer_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[LocationKind] = mapped_column(
        SAEnum(LocationKind, name="location_kind"), nullable=False
    )
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
