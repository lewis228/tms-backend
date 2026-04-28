# src/street_turn/model.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Text, ForeignKey, DateTime,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from street_turn.const.link_type import StreetTurnLinkType
from street_turn.const.status import StreetTurnStatus


class StreetTurnModel(Base, TeamScopedMixin):
    """Street turn — Import 컨테이너를 Export 에 직접 사용 (port 회수 절감).

    H-8: 승인 워크플로우 추가.
    상태: REQUESTED → APPROVED / REJECTED / CANCELLED.
    승인 완료 시 service 가 container_event(STREET_TURNED) 자동 기록.
    """
    __tablename__ = "street_turn"

    import_order_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_order.id", ondelete="RESTRICT"), nullable=False,
    )
    export_order_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_order.id", ondelete="RESTRICT"), nullable=False,
    )
    # H-8: container_number string 유지 (호환). H-1 이후 컨테이너 정규화로 container_id 도 추가.
    container_number: Mapped[str | None] = mapped_column(String(11), nullable=True)
    container_id: Mapped[int | None] = mapped_column(
        ForeignKey("container.id", ondelete="SET NULL"), nullable=True,
    )
    link_type: Mapped[StreetTurnLinkType] = mapped_column(
        SAEnum(StreetTurnLinkType, name="street_turn_link_type"),
        default=StreetTurnLinkType.MANUAL,
        nullable=False,
    )

    # ── H-8: 승인 워크플로우 ─────────────────────────────────────
    status: Mapped[StreetTurnStatus] = mapped_column(
        SAEnum(StreetTurnStatus, name="street_turn_status"),
        default=StreetTurnStatus.REQUESTED,
        server_default=StreetTurnStatus.REQUESTED.value,
        nullable=False,
    )
    carrier_approval_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True,
    )
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_street_turn_team_id_id"),
        UniqueConstraint("import_order_id", name="uq_street_turn_import"),
        UniqueConstraint("export_order_id", name="uq_street_turn_export"),
        Index("ix_street_turn_team_container", "team_id", "container_number"),
        Index("ix_street_turn_team_container_id", "team_id", "container_id"),
        Index("ix_street_turn_team_status", "team_id", "status"),
        Index("ix_street_turn_team_active_id", "team_id", "is_active", "id"),
        Index("ix_street_turn_team_updated_at", "team_id", "updated_at"),
    )
