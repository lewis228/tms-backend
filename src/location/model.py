# src/location/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Numeric, Text, Index, UniqueConstraint, ForeignKey,
    Enum as SAEnum,
)
from decimal import Decimal

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from location.const.kind import LocationKind


class LocationModel(Base, TeamScopedMixin):
    """장소 (Team-Scoped) — 야드/고객사 주소/항만 등."""
    __tablename__ = "location"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[LocationKind] = mapped_column(
        SAEnum(LocationKind, name="location_kind"),
        default=LocationKind.YARD,
        server_default=LocationKind.YARD.value,
        nullable=False,
    )
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 전역 zip 마스터 참조 — 정산 dest 자동채움(city/state 조인)에 사용
    zip_id: Mapped[int | None] = mapped_column(
        ForeignKey("zip_code.id", ondelete="SET NULL"), nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_location_team_id_id"),
        Index("ix_location_team_active_id", "team_id", "is_active", "id"),
        Index("ix_location_team_kind", "team_id", "kind"),
        Index("ix_location_team_customer", "team_id", "customer_id"),
        Index("ix_location_team_name",       "team_id", "name"),
        Index("ix_location_team_updated_at", "team_id", "updated_at"),
        Index("ix_location_team_zip", "team_id", "zip_id"),
    )
