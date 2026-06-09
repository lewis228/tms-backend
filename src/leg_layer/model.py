# src/leg_layer/model.py
"""Leg 3-Layer 부가 구조 (라인 테이블 3종) — 기존 leg 에 additive.

컨플루언스 Leg 유형 분석:
- Layer 2 Add-on   → leg_addon (복수)
- Layer 3 Charge Event → leg_charge_event (토글 + Free Time)
- Leg 내 경유지     → leg_stop_off (독립 leg 아님)

모두 leg(team_id, id) 복합 FK. leg 본체 재설계와 무관하게 leg PK 만 유지되면 호환.
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Boolean, JSON, Numeric, DateTime, ForeignKey,
    Index, UniqueConstraint, ForeignKeyConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from leg_layer.const.status import LegAddonCode, LegChargeEventCode


class LegAddonModel(Base, TeamScopedMixin):
    """Layer 2 — Leg 의 Add-on (복수). amount_override 있으면 수동 금액."""
    __tablename__ = "leg_addon"
    __with_team_rel__ = False

    leg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[LegAddonCode] = mapped_column(SAEnum(LegAddonCode, name="leg_addon_code"), nullable=False)
    amount_override: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_addon_team_id_id"),
        UniqueConstraint("team_id", "leg_id", "code", name="uq_leg_addon_leg_code"),
        ForeignKeyConstraint(["team_id", "leg_id"], ["leg.team_id", "leg.id"],
                             ondelete="CASCADE", name="fk_leg_addon_leg_team_id_id"),
        Index("ix_leg_addon_team_id_id", "team_id", "id"),
        Index("ix_leg_addon_team_leg", "team_id", "leg_id"),
    )


class LegChargeEventModel(Base, TeamScopedMixin):
    """Layer 3 — Charge Event (토글 + Free Time). 초과분 = (실체류 - free) × 단가(정산 시)."""
    __tablename__ = "leg_charge_event"
    __with_team_rel__ = False

    leg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[LegChargeEventCode] = mapped_column(SAEnum(LegChargeEventCode, name="leg_charge_event_code"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    free_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    free_days:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 실체류(분)
    actual_days:    Mapped[int | None] = mapped_column(Integer, nullable=True)  # 실체류(일)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_charge_event_team_id_id"),
        UniqueConstraint("team_id", "leg_id", "code", name="uq_leg_charge_event_leg_code"),
        ForeignKeyConstraint(["team_id", "leg_id"], ["leg.team_id", "leg.id"],
                             ondelete="CASCADE", name="fk_leg_charge_event_leg_team_id_id"),
        Index("ix_leg_charge_event_team_id_id", "team_id", "id"),
        Index("ix_leg_charge_event_team_leg", "team_id", "leg_id"),
    )


class LegStopOffModel(Base, TeamScopedMixin):
    """Leg 내 경유지 (독립 leg 아님). seq 순서 + 도착/출발/서명/POD."""
    __tablename__ = "leg_stop_off"
    __with_team_rel__ = False

    leg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("location.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)  # ad-hoc 경유지명
    arrived_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    pod_file_id: Mapped[int | None] = mapped_column(ForeignKey("file_asset.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_stop_off_team_id_id"),
        ForeignKeyConstraint(["team_id", "leg_id"], ["leg.team_id", "leg.id"],
                             ondelete="CASCADE", name="fk_leg_stop_off_leg_team_id_id"),
        Index("ix_leg_stop_off_team_id_id", "team_id", "id"),
        Index("ix_leg_stop_off_team_leg", "team_id", "leg_id"),
    )
