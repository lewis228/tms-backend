# src/rate_point/model.py
from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Text, Numeric, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from rate_point.const.status import PointType


class RatePointModel(Base, TeamScopedMixin):
    """요율표의 행(Point) — Terminal/Yard 통합 마스터 (Team-Scoped).

    컨플루언스 요율표 기획: Point(Terminal/Yard)가 Rate Sheet 의 행.
    Point 가 추가되면 해당 Point 를 행으로 하는 Rate Sheet 슬롯이 자동 생성된다(Phase 2).
    기존 terminal/location 마스터와는 optional FK 로만 연결 — 요율 전용 라이프사이클 분리.
    """
    __tablename__ = "rate_point"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    point_type: Mapped[PointType] = mapped_column(
        SAEnum(PointType, name="rate_point_type"),
        nullable=False,
    )

    address:   Mapped[str | None]     = mapped_column(String(500), nullable=True)
    latitude:  Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)

    # ── 기존 마스터 연결 (옵션) — 도메인 간 FK, 삭제돼도 참조만 끊김 ──
    terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminal.id", ondelete="SET NULL"), nullable=True,
    )
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_point_team_id_id"),
        UniqueConstraint("team_id", "code", name="uq_rate_point_team_code"),
        Index("ix_rate_point_team_active_id", "team_id", "is_active", "id"),
        Index("ix_rate_point_team_type",       "team_id", "point_type"),
        Index("ix_rate_point_team_name",       "team_id", "name"),
        Index("ix_rate_point_team_updated_at", "team_id", "updated_at"),
    )
