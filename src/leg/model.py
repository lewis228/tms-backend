# src/leg/model.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Boolean, Text, ForeignKey, DateTime,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from delivery_order.const.status import DeliveryStatus
from leg.const.status import LegStatus, MoveType, ServiceType


class LegModel(Base, TeamScopedMixin):
    """Leg = D/O 의 한 단계 운송 (Movement + Assignment 통합)."""
    __tablename__ = "leg"

    delivery_order_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_order.id", ondelete="CASCADE"), nullable=False,
    )

    # 어떤 단계의 leg 인지 (D/O 상태 기준)
    step: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"), nullable=False,
    )

    move_type: Mapped[MoveType] = mapped_column(
        SAEnum(MoveType, name="move_type"), nullable=False,
    )
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="service_type"), nullable=False,
    )

    status: Mapped[LegStatus] = mapped_column(
        SAEnum(LegStatus, name="leg_status"),
        default=LegStatus.PENDING,
        server_default=LegStatus.PENDING.value,
        nullable=False,
    )

    # ── 배차 / 위치 ─────────────────────────────────────────────
    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="SET NULL"), nullable=True,
    )
    pickup_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    pickup_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── 진행 시각 ───────────────────────────────────────────────
    started_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── 정산 ────────────────────────────────────────────────────
    storage_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_settled:   Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlement.id", ondelete="SET NULL"), nullable=True,
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_team_id_id"),
        Index("ix_leg_team_do",       "team_id", "delivery_order_id"),
        Index("ix_leg_team_driver",   "team_id", "driver_id"),
        Index("ix_leg_team_status",   "team_id", "status"),
        Index("ix_leg_team_pickup",   "team_id", "pickup_date"),
        Index("ix_leg_team_active_id","team_id", "is_active", "id"),
        Index("ix_leg_team_updated_at","team_id", "updated_at"),
    )
