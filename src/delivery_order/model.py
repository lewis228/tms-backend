# src/delivery_order/model.py
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Boolean, Text, ForeignKey, DateTime, Date,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin
from delivery_order.const.status import (
    DeliveryStatus, ShipmentDirection, ContainerSize,
)


class DeliveryOrderModel(Base, TenantScopedMixin):
    """D/O (Tenant-Scoped). 상태 머신 + 게이트는 service 에서."""
    __tablename__ = "delivery_order"

    # ── 상태 / 방향 ─────────────────────────────────────────────
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"),
        default=DeliveryStatus.PLANNING,
        server_default=DeliveryStatus.PLANNING.value,
        nullable=False,
    )
    direction: Mapped[ShipmentDirection] = mapped_column(
        SAEnum(ShipmentDirection, name="shipment_direction"),
        nullable=False,
    )

    # ── 식별 / 참조 ─────────────────────────────────────────────
    bl_number:      Mapped[str | None] = mapped_column(String(64), nullable=True)
    booking_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference:      Mapped[str | None] = mapped_column(String(120), nullable=True)

    # ── FK ──────────────────────────────────────────────────────
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False,
    )
    terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminal.id", ondelete="SET NULL"), nullable=True,
    )
    vessel_id: Mapped[int | None] = mapped_column(
        ForeignKey("vessel.id", ondelete="SET NULL"), nullable=True,
    )
    delivery_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    return_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 컨테이너 ───────────────────────────────────────────────
    container_number: Mapped[str | None] = mapped_column(String(11), nullable=True)
    container_size: Mapped[ContainerSize | None] = mapped_column(
        SAEnum(ContainerSize, name="container_size"), nullable=True,
    )
    container_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chassis_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # ── 일정 ────────────────────────────────────────────────────
    eta:                  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_appointment:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_appointment: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_appointment:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── LFD / 일자 ──────────────────────────────────────────────
    demurrage_lfd: Mapped[date | None] = mapped_column(Date, nullable=True)
    detention_lfd: Mapped[date | None] = mapped_column(Date, nullable=True)
    empty_date:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    loaded_date:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── 게이트 플래그 ───────────────────────────────────────────
    bl_released:     Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    pier_pass_paid:  Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    customs_cleared: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    # ── 메모 ────────────────────────────────────────────────────
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_delivery_order_tenant_id_id"),
        Index("ix_do_tenant_status",         "tenant_id", "status"),
        Index("ix_do_tenant_direction",      "tenant_id", "direction"),
        Index("ix_do_tenant_customer",       "tenant_id", "customer_id"),
        Index("ix_do_tenant_container",      "tenant_id", "container_number"),
        Index("ix_do_tenant_active_id",      "tenant_id", "is_active", "id"),
        Index("ix_do_tenant_demurrage_lfd",  "tenant_id", "demurrage_lfd"),
        Index("ix_do_tenant_detention_lfd",  "tenant_id", "detention_lfd"),
        Index("ix_do_tenant_updated_at",     "tenant_id", "updated_at"),
    )
