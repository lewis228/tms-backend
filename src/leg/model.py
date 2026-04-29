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
from leg.const.status import LegStatus, MoveType, ServiceType, LegKind, MoveTypeV3


class LegModel(Base, TeamScopedMixin):
    """Leg = D/O 의 한 단계 운송 (Movement + Assignment 통합)."""
    __tablename__ = "leg"

    delivery_order_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_order.id", ondelete="CASCADE"), nullable=False,
    )

    # 컨테이너 단위 leg (Bobtail / Dry-Run leg 는 NULL 허용)
    container_id: Mapped[int | None] = mapped_column(
        ForeignKey("container.id", ondelete="SET NULL"), nullable=True,
    )

    # ── v3 Stop 시퀀스 FK (container_stop 참조) ─────────────
    # Leg = "from_stop → to_stop" 사이의 이동.
    # 차고→ORIGIN 같은 첫 leg 도 from_stop=차고 stop / to_stop=터미널 stop 으로 표현.
    # 마이그레이션 직후 백필 전이라 우선 nullable, 백필 후 NOT NULL 으로 좁힐 예정.
    from_stop_id: Mapped[int | None] = mapped_column(
        ForeignKey("container_stop.id", ondelete="SET NULL"), nullable=True,
    )
    to_stop_id: Mapped[int | None] = mapped_column(
        ForeignKey("container_stop.id", ondelete="SET NULL"), nullable=True,
    )

    # 어떤 단계의 leg 인지 (D/O 상태 기준)
    step: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"), nullable=False,
    )

    move_type: Mapped[MoveType] = mapped_column(
        SAEnum(MoveType, name="move_type"), nullable=False,
    )
    # ── v3 4축 형상 (TRUCK_ONLY/CHASSIS_ONLY/EMPTY_LOADED/FULL_LOADED) ─────
    # 기존 move_type 은 H-7 까지 호환 유지. v3 부터 신규 컬럼으로 표현.
    move_type_v3: Mapped[MoveTypeV3 | None] = mapped_column(
        SAEnum(MoveTypeV3, name="move_type_v3"), nullable=True,
    )
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="service_type"), nullable=False,
    )
    # H-6: leg 동작 분류 (Manifest 의 한 줄 = 1 leg = 1 kind).
    leg_kind: Mapped[LegKind | None] = mapped_column(
        SAEnum(LegKind, name="leg_kind"), nullable=True,
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
    # H-3: 트럭 자산 분리. leg 마다 다른 트럭 가능.
    truck_id: Mapped[int | None] = mapped_column(
        ForeignKey("truck.id", ondelete="SET NULL"), nullable=True,
    )
    # H-4: 챠시 자산 분리. chassis_id 는 leg 의 default chassis 로 유지.
    chassis_id: Mapped[int | None] = mapped_column(
        ForeignKey("chassis.id", ondelete="SET NULL"), nullable=True,
    )
    # H-6: 챠시-컨 swap 추적. start ≠ end 면 챠시 flip 발생.
    chassis_at_start_id: Mapped[int | None] = mapped_column(
        ForeignKey("chassis.id", ondelete="SET NULL"), nullable=True,
    )
    chassis_at_end_id: Mapped[int | None] = mapped_column(
        ForeignKey("chassis.id", ondelete="SET NULL"), nullable=True,
    )
    container_at_start_id: Mapped[int | None] = mapped_column(
        ForeignKey("container.id", ondelete="SET NULL"), nullable=True,
    )
    container_at_end_id: Mapped[int | None] = mapped_column(
        ForeignKey("container.id", ondelete="SET NULL"), nullable=True,
    )
    remarks: Mapped[str | None] = mapped_column(String(500), nullable=True)
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
        Index("ix_leg_team_do",        "team_id", "delivery_order_id"),
        Index("ix_leg_team_container", "team_id", "container_id"),
        Index("ix_leg_team_driver",    "team_id", "driver_id"),
        Index("ix_leg_team_truck",     "team_id", "truck_id"),
        Index("ix_leg_team_chassis",   "team_id", "chassis_id"),
        Index("ix_leg_team_kind",      "team_id", "leg_kind"),
        Index("ix_leg_team_status",    "team_id", "status"),
        Index("ix_leg_team_pickup",    "team_id", "pickup_date"),
        Index("ix_leg_team_active_id", "team_id", "is_active", "id"),
        Index("ix_leg_team_updated_at","team_id", "updated_at"),
    )
