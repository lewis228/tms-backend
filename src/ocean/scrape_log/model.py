from __future__ import annotations
from typing import Optional, Any
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import (
    String, Integer, DateTime, Text, JSON, Index, UniqueConstraint, ForeignKeyConstraint, and_,
)
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings


class ScrapeLogModel(Base, TeamScopedMixin):
    """스크래핑 실행 로그. Shipment 의 자식 라인 — 이력 보관 목적."""

    __tablename__ = "ocean_scrape_logs"
    __with_team_rel__ = False

    shipment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    result_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── 관계 ────────────────────────────────────────────────
    shipment = relationship(
        "ShipmentModel",
        back_populates="scrape_logs",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(ScrapeLogModel.team_id) == __import__("ocean.shipment.model", fromlist=["ShipmentModel"]).ShipmentModel.team_id,
            foreign(ScrapeLogModel.shipment_id) == __import__("ocean.shipment.model", fromlist=["ShipmentModel"]).ShipmentModel.id,
        ),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "shipment_id"],
            ["ocean_shipments.team_id", "ocean_shipments.id"],
            ondelete="CASCADE",
            name="fk_ocean_scrape_logs_shipment_team_id_id",
        ),
        UniqueConstraint("team_id", "id", name="uq_ocean_scrape_logs_team_id_id"),
        Index("ix_ocean_scrape_logs_team_id_id", "team_id", "id"),
        Index("ix_ocean_scrape_logs_team_shipment", "team_id", "shipment_id"),
        Index("ix_ocean_scrape_logs_team_scraped_at", "team_id", "scraped_at"),
    )
