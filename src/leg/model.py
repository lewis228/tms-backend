# src/leg/model.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Boolean, Text, ForeignKey, DateTime, Numeric,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from delivery_order.const.status import DeliveryStatus
from leg.const.status import (
    LegStatus, MoveType, ServiceType, PointType, LegMoveCode,
)


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

    # ── 포인트 모델: Leg = from_point → to_point 간선 ───────────────
    # 사용자가 '레그 추가' 시 컨테이너 포인트(container_stop) 중 from/to 를 고른다.
    # from/to_location_type 은 그 포인트의 point_type 스냅샷(읽기전용, 가격엔 미사용).
    from_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("container_stop.id", ondelete="SET NULL"), nullable=True,
    )
    to_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("container_stop.id", ondelete="SET NULL"), nullable=True,
    )
    from_location_type: Mapped[PointType | None] = mapped_column(
        SAEnum(PointType, name="leg_from_location_type"), nullable=True,
    )
    to_location_type: Mapped[PointType | None] = mapped_column(
        SAEnum(PointType, name="leg_to_location_type"), nullable=True,
    )
    move_code: Mapped[LegMoveCode | None] = mapped_column(
        SAEnum(LegMoveCode, name="leg_move_code"), nullable=True,
    )

    # ── 재설계: 요율 해석 입력 (RateResolver 가 사용) ──────────────
    # row_point(터미널/야드) + 목적지(zip/city) + 거리/시간. 정산 시 driver→그룹→method 로 해석.
    rate_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("rate_point.id", ondelete="SET NULL"), nullable=True,
    )
    dest_zip:   Mapped[str | None] = mapped_column(String(16), nullable=True)
    dest_city:  Mapped[str | None] = mapped_column(String(120), nullable=True)
    dest_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    rate_miles: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)  # MILE 방식
    rate_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)   # HOURLY 방식

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
    # 픽업/배송 위치는 from_point/to_point(container_stop)가 대체. 날짜(스케줄)만 leg 에 유지.
    pickup_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── 진행 시각 ───────────────────────────────────────────────
    assigned_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 재설계: ASSIGNED 진입
    started_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Dry Run 재발급 (빠꾸 → 새 leg) ──────────────────────────
    # 이 leg 가 어떤 DRY_RUN leg 에서 재발급됐는지(원본 leg.id). 같은 도메인 self-ref → 단순 int.
    reissued_from_leg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Mobile 수락 / 거절 (Driver app) ──────────────────────
    # driver 에게 offered 된 시각 (driver_id 가 세팅된 시각). NULL 이면 미할당.
    offered_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # driver 가 수락한 시각. NULL = 미수락
    accepted_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # driver 가 거절한 시각. NULL = 미거절
    rejected_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── 정산 ────────────────────────────────────────────────────
    # 정산은 payroll(payroll_line.leg_id 역참조)이 담당한다.
    storage_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    is_settled:   Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_team_id_id"),
        Index("ix_leg_team_do",        "team_id", "delivery_order_id"),
        Index("ix_leg_team_container", "team_id", "container_id"),
        Index("ix_leg_team_driver",    "team_id", "driver_id"),
        Index("ix_leg_team_truck",     "team_id", "truck_id"),
        Index("ix_leg_team_chassis",   "team_id", "chassis_id"),
        Index("ix_leg_team_from_point", "team_id", "from_point_id"),
        Index("ix_leg_team_to_point",   "team_id", "to_point_id"),
        Index("ix_leg_team_status",    "team_id", "status"),
        Index("ix_leg_team_pickup",    "team_id", "pickup_date"),
        Index("ix_leg_team_active_id", "team_id", "is_active", "id"),
        Index("ix_leg_team_updated_at","team_id", "updated_at"),
        # Mobile: driver 별 미수락 leg 빠른 조회
        Index("ix_leg_team_driver_offered", "team_id", "driver_id", "offered_at", "accepted_at"),
    )
