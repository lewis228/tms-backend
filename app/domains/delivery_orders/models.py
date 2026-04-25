"""DeliveryOrder 모델 — TMS 핵심 도메인."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin
from app.models.enums import ContainerSize, DeliveryStatus, ShipmentDirection


class DeliveryOrder(TenantAuditMixin, Base):
    __tablename__ = "delivery_orders"
    __table_args__ = (
        Index("ix_do_tenant_status", "tenant_id", "status"),
        Index("ix_do_tenant_container", "tenant_id", "container_number"),
        Index("ix_do_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_do_tenant_terminal", "tenant_id", "terminal_id"),
        Index("ix_do_tenant_created", "tenant_id", "created_at"),
    )

    # 상태 + 방향
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"),
        nullable=False,
        default=DeliveryStatus.PLANNING,
    )
    direction: Mapped[ShipmentDirection] = mapped_column(
        SAEnum(ShipmentDirection, name="shipment_direction"), nullable=False
    )

    # 식별자
    bl_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    booking_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # 관계
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    terminal_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("terminals.id", ondelete="SET NULL"), nullable=True
    )
    vessel_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("vessels.id", ondelete="SET NULL"), nullable=True
    )
    delivery_location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    return_location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )

    # 컨테이너
    container_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    container_size: Mapped[ContainerSize | None] = mapped_column(
        SAEnum(ContainerSize, name="container_size"), nullable=True
    )
    container_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chassis_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # 일정
    eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_appointment: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_appointment: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_appointment: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    demurrage_lfd: Mapped[date | None] = mapped_column(Date, nullable=True)
    detention_lfd: Mapped[date | None] = mapped_column(Date, nullable=True)
    empty_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    loaded_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 게이트 플래그
    bl_released: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pier_pass_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    customs_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
