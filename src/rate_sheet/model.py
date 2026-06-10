# src/rate_sheet/model.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import (
    String, Text, Numeric, Date, Integer, ForeignKey,
    Index, UniqueConstraint, ForeignKeyConstraint, and_, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings
from rate_sheet.const.status import (
    SheetKind, RateMoveType, RateServiceType, RateContainerSize, RateEntrySource, RateEntryAction,
)


class RateSheetModel(Base, TeamScopedMixin):
    """요율표 슬롯 (헤더) — (rate_group, kind, move_type, service_type) 단위.

    재설계(Zone×Zone): 한 슬롯 = 한 (MoveType, ServiceType) 매트릭스. 셀(rate_entry)이
    from→to(zone/city) 좌표를 가진다. kind 는 group.method 와 동일(편의 denormalize).
    MILE/HOURLY 는 move/service NULL 단일 슬롯(per_unit). row_point 개념 폐기.
    """
    __tablename__ = "rate_sheet"

    rate_group_id: Mapped[int] = mapped_column(
        ForeignKey("rate_group.id", ondelete="RESTRICT"), nullable=False,
    )
    kind: Mapped[SheetKind] = mapped_column(SAEnum(SheetKind, name="rate_sheet_kind"), nullable=False)
    move_type: Mapped[RateMoveType | None] = mapped_column(
        SAEnum(RateMoveType, name="rate_move_type"), nullable=True,  # MILE/HOURLY 는 None
    )
    # 같은 From→To·Move 라도 Service Type(Live/Drop/None) 별 요율 분리.
    service_type: Mapped[RateServiceType | None] = mapped_column(
        SAEnum(RateServiceType, name="rate_service_type"), nullable=True,  # MILE/HOURLY·미지정 None
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    entries: Mapped[list["RateEntryModel"]] = relationship(
        "RateEntryModel",
        back_populates="sheet",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(RateEntryModel.team_id) == RateSheetModel.team_id,
            foreign(RateEntryModel.rate_sheet_id) == RateSheetModel.id,
        ),
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_sheet_team_id_id"),
        UniqueConstraint(
            "team_id", "rate_group_id", "kind", "move_type", "service_type",
            name="uq_rate_sheet_slot",
        ),
        Index("ix_rate_sheet_team_active_id", "team_id", "is_active", "id"),
        Index("ix_rate_sheet_team_group",      "team_id", "rate_group_id"),
        Index("ix_rate_sheet_team_kind",       "team_id", "kind"),
        Index("ix_rate_sheet_team_updated_at",  "team_id", "updated_at"),
    )


class RateEntryModel(Base, TeamScopedMixin):
    """요율 셀 (라인, append-only 유효일자 버전).

    하나의 (sheet, 셀 좌표) 에 대해 effective_from 별로 여러 버전이 누적된다.
    절대 UPDATE 하지 않고 close(effective_to) + 새 row insert 로 버전 관리.
    셀 좌표 = (from_zone_id→to_zone_id) ZONE | (from_city/state→to_city/state) CITY + container_size.
    MILE/HOURLY 시트는 좌표 없이 per_unit 단일 셀.
    """
    __tablename__ = "rate_entry"
    __with_team_rel__ = False

    rate_sheet_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── 셀 좌표 (kind 에 따라 zone 쌍 또는 city 쌍 사용; MILE/HOURLY 는 둘 다 NULL) ──
    from_zone_id: Mapped[int | None] = mapped_column(ForeignKey("rate_zone.id", ondelete="SET NULL"), nullable=True)
    to_zone_id:   Mapped[int | None] = mapped_column(ForeignKey("rate_zone.id", ondelete="SET NULL"), nullable=True)
    from_city:  Mapped[str | None] = mapped_column(String(120), nullable=True)
    from_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    to_city:    Mapped[str | None] = mapped_column(String(120), nullable=True)
    to_state:   Mapped[str | None] = mapped_column(String(8), nullable=True)
    container_size: Mapped[RateContainerSize | None] = mapped_column(
        SAEnum(RateContainerSize, name="rate_container_size"), nullable=True,
    )

    # ── 값 ─────────────────────────────────────────────────────
    amount:   Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)  # 매트릭스/Point×Point
    per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)  # MILE/HOURLY 단가

    # ── 유효기간 (append-only 버전) ─────────────────────────────
    effective_from: Mapped[date]        = mapped_column(Date, nullable=False)
    effective_to:   Mapped[date | None] = mapped_column(Date, nullable=True)  # None = 현재 유효(무제한)

    source: Mapped[RateEntrySource] = mapped_column(
        SAEnum(RateEntrySource, name="rate_entry_source"),
        default=RateEntrySource.SHEET, server_default=RateEntrySource.SHEET.value, nullable=False,
    )
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    sheet: Mapped["RateSheetModel"] = relationship(
        "RateSheetModel",
        back_populates="entries",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(RateEntryModel.team_id) == RateSheetModel.team_id,
            foreign(RateEntryModel.rate_sheet_id) == RateSheetModel.id,
        ),
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_entry_team_id_id"),
        ForeignKeyConstraint(
            ["team_id", "rate_sheet_id"],
            ["rate_sheet.team_id", "rate_sheet.id"],
            ondelete="CASCADE",
            name="fk_rate_entry_sheet_team_id_id",
        ),
        Index("ix_rate_entry_team_id_id", "team_id", "id"),
        # 핫패스: 시트+from존+to존+사이즈+유효시작일 lookup
        Index("ix_rate_entry_lookup", "team_id", "rate_sheet_id", "from_zone_id", "to_zone_id", "container_size", "effective_from"),
        Index("ix_rate_entry_team_sheet", "team_id", "rate_sheet_id"),
        Index("ix_rate_entry_team_city", "team_id", "from_city", "from_state", "to_city", "to_state"),
        Index("ix_rate_entry_team_active", "team_id", "is_active"),
    )


class RateEntryHistoryModel(Base, TeamScopedMixin):
    """요율 변경 이력 (라인, append-only) — '언제 누가 무엇을 얼마→얼마' 추적."""
    __tablename__ = "rate_entry_history"
    __with_team_rel__ = False

    rate_sheet_id:  Mapped[int]        = mapped_column(Integer, nullable=False)
    rate_entry_id:  Mapped[int | None] = mapped_column(Integer, nullable=True)  # 새로 생성/대상 셀 id

    # 셀 좌표 (스냅샷)
    from_zone_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_zone_id:   Mapped[int | None] = mapped_column(Integer, nullable=True)
    from_city:  Mapped[str | None] = mapped_column(String(120), nullable=True)
    from_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
    to_city:    Mapped[str | None] = mapped_column(String(120), nullable=True)
    to_state:   Mapped[str | None] = mapped_column(String(8), nullable=True)
    container_size: Mapped[RateContainerSize | None] = mapped_column(
        SAEnum(RateContainerSize, name="rate_container_size_hist"), nullable=True,
    )

    old_amount:   Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    new_amount:   Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    old_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    new_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    action: Mapped[RateEntryAction] = mapped_column(
        SAEnum(RateEntryAction, name="rate_entry_action"), nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_entry_history_team_id_id"),
        ForeignKeyConstraint(
            ["team_id", "rate_sheet_id"],
            ["rate_sheet.team_id", "rate_sheet.id"],
            ondelete="CASCADE",
            name="fk_rate_entry_history_sheet_team_id_id",
        ),
        Index("ix_rate_entry_history_team_id_id", "team_id", "id"),
        Index("ix_rate_entry_history_team_sheet", "team_id", "rate_sheet_id", "created_at"),
    )
