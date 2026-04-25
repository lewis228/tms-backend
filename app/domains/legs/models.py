"""Leg 모델 (Movement + LegAssignment 통합).

D/O 의 한 단계 이동(픽업→배달, 배달→야드 등)을 한 행으로 표현.
- step: 이 Leg 가 진행하는 D/O 의 다음 단계 (DeliveryStatus 사용)
- driver_id: PENDING 상태에서는 null 가능. DISPATCHED 시 필수.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantAuditMixin
from app.models.enums import DeliveryStatus, LegStatus, MoveType, ServiceType


class Leg(TenantAuditMixin, Base):
    __tablename__ = "legs"
    __table_args__ = (
        Index("ix_legs_tenant_do", "tenant_id", "delivery_order_id"),
        Index("ix_legs_tenant_driver_status", "tenant_id", "driver_id", "status"),
        Index("ix_legs_tenant_status", "tenant_id", "status"),
    )

    delivery_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("delivery_orders.id", ondelete="CASCADE"), nullable=False
    )
    step: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"), nullable=False
    )
    move_type: Mapped[MoveType] = mapped_column(
        SAEnum(MoveType, name="move_type"), nullable=False
    )
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="service_type"), nullable=False
    )
    status: Mapped[LegStatus] = mapped_column(
        SAEnum(LegStatus, name="leg_status"),
        nullable=False,
        default=LegStatus.PENDING,
    )

    driver_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )

    pickup_location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    pickup_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    delivery_location_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    storage_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yard_in_date: Mapped[date | None] = mapped_column(DateTime(timezone=True), nullable=True)
    yard_out_date: Mapped[date | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_settled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settlement_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("settlements.id", ondelete="SET NULL", use_alter=True, name="fk_legs_settlement"),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
