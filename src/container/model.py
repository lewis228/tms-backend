# src/container/model.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Boolean, Text, ForeignKey, DateTime, Date, Numeric,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from container.const.status import (
    ContainerStatus, ContainerSize, ContainerEventKind,
)
from leg.const.status import ServiceType


class ContainerModel(Base, TeamScopedMixin):
    """D/O 1 ─ Container N. 컨테이너별 destination/seal/weight/LFD/service_type."""
    __tablename__ = "container"

    delivery_order_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_order.id", ondelete="CASCADE"), nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    # ── 식별 ─────────────────────────────────────────────
    container_number: Mapped[str | None] = mapped_column(String(11), nullable=True)
    seal_no:          Mapped[str | None] = mapped_column(String(64), nullable=True)
    size:             Mapped[ContainerSize | None] = mapped_column(
        SAEnum(ContainerSize, name="container_size"), nullable=True,
    )
    type:             Mapped[str | None] = mapped_column(String(32), nullable=True)
    weight_kg:        Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # 챠시 (H-4: chassis 마스터 FK 로 정규화. NULL 허용 — 풀에서 빌릴 때만 의미 있음)
    chassis_id: Mapped[int | None] = mapped_column(
        ForeignKey("chassis.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 일정 (컨테이너별로 다를 수 있음) ─────
    pickup_appointment:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_appointment: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_appointment:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    demurrage_lfd:        Mapped[date | None]     = mapped_column(Date, nullable=True)
    detention_lfd:        Mapped[date | None]     = mapped_column(Date, nullable=True)
    empty_date:           Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    loaded_date:          Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── 위치 (D/O 에서 옮겨옴) ─────
    delivery_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    return_location_id:   Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 서비스 방식 (컨테이너별) ─────
    service_type: Mapped[ServiceType | None] = mapped_column(
        SAEnum(ServiceType, name="service_type"), nullable=True,
    )

    # ── 진행 게이트 ─────
    pier_pass_paid:  Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    customs_cleared: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    # ── 상태머신 (D/O 와 같은 enum 재사용. 디스패처 수동 변경 가능) ─────
    status: Mapped[ContainerStatus] = mapped_column(
        SAEnum(ContainerStatus, name="delivery_status"),
        default=ContainerStatus.PLANNING,
        server_default=ContainerStatus.PLANNING.value,
        nullable=False,
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_container_team_id_id"),
        UniqueConstraint("delivery_order_id", "sequence_no", name="uq_container_do_seq"),
        Index("ix_container_team_do",          "team_id", "delivery_order_id"),
        Index("ix_container_team_number",      "team_id", "container_number"),
        Index("ix_container_team_status",      "team_id", "status"),
        Index("ix_container_team_demurrage",   "team_id", "demurrage_lfd"),
        Index("ix_container_team_detention",   "team_id", "detention_lfd"),
        Index("ix_container_team_active_id",   "team_id", "is_active", "id"),
        Index("ix_container_team_updated_at",  "team_id", "updated_at"),
    )


class ContainerEventModel(Base, TeamScopedMixin):
    """컨테이너 라이프사이클 이벤트 로그 (append-only)."""
    __tablename__ = "container_event"

    container_id: Mapped[int] = mapped_column(
        ForeignKey("container.id", ondelete="CASCADE"), nullable=False,
    )
    leg_id: Mapped[int | None] = mapped_column(
        ForeignKey("leg.id", ondelete="SET NULL"), nullable=True,
    )
    event_kind: Mapped[ContainerEventKind] = mapped_column(
        SAEnum(ContainerEventKind, name="container_event_kind"), nullable=False,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note:        Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_container_event_team_id_id"),
        Index("ix_container_event_team_container", "team_id", "container_id", "occurred_at"),
        Index("ix_container_event_team_kind",      "team_id", "event_kind"),
        Index("ix_container_event_team_active_id", "team_id", "is_active", "id"),
    )
