# src/delivery_order/model.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Boolean, Text, ForeignKey, DateTime,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from delivery_order.const.status import (
    DeliveryStatus, ShipmentDirection,
)


class DeliveryOrderModel(Base, TeamScopedMixin):
    """D/O 헤더 (Team-Scoped). 컨테이너는 ContainerModel 1:N 으로 분리."""
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

    # ── 일정 (헤더 단위 — 컨테이너 단위 일정은 ContainerModel) ─────
    eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── 게이트 (BL 단위) ────────────────────────────────────────
    bl_released: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    # ── 메모 ────────────────────────────────────────────────────
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_delivery_order_team_id_id"),
        Index("ix_do_team_status",         "team_id", "status"),
        Index("ix_do_team_direction",      "team_id", "direction"),
        Index("ix_do_team_customer",       "team_id", "customer_id"),
        Index("ix_do_team_active_id",      "team_id", "is_active", "id"),
        Index("ix_do_team_updated_at",     "team_id", "updated_at"),
    )
