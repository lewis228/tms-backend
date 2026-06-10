# src/delivery_order/model.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Boolean, Text, ForeignKey, DateTime, Integer, Numeric, JSON,
    Index, UniqueConstraint, ForeignKeyConstraint, Enum as SAEnum,
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

    # ── Hold / Cancel (워크플로우 status 와 직교한 overlay) ───────
    # Hold 는 어느 단계서든 걸고 풀 수 있는 오버레이(자동 파생 일시정지). Cancel 은 사실상 종료.
    is_on_hold:   Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    hold_reason:  Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

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


class DeliveryOrderAddonModel(Base, TeamScopedMixin):
    """D/O 단위 추가요금 인스턴스 (중복 가능). addon_id=타입, code=addon.code 스냅샷, amount=확정.

    leg_addon 과 별개 — 부착 위치(leg vs D/O)가 곧 청구 단위. 고객 청구(invoice)에 자동 가산.
    """
    __tablename__ = "delivery_order_addon"
    __with_team_rel__ = False

    delivery_order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    addon_id: Mapped[int | None] = mapped_column(ForeignKey("addon.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False)  # addon.code 스냅샷
    quantity:    Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1, server_default="1", nullable=False)
    unit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount:      Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_do_addon_team_id_id"),
        ForeignKeyConstraint(["team_id", "delivery_order_id"],
                             ["delivery_order.team_id", "delivery_order.id"],
                             ondelete="CASCADE", name="fk_do_addon_do_team_id_id"),
        Index("ix_do_addon_team_id_id", "team_id", "id"),
        Index("ix_do_addon_team_do", "team_id", "delivery_order_id"),
    )
