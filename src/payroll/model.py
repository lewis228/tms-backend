# src/payroll/model.py
"""드라이버 정산(Payroll) — RateResolver 기반.

settlement(헤더: driver+기간) + payroll_line(leg snapshot, 요율 동결) + payroll_charge(addon).
요율은 정산 시점에 RateResolver 가 해석해 라인에 동결(snapshot)한다.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import (
    String, Integer, Numeric, Date, JSON, ForeignKey,
    Index, UniqueConstraint, ForeignKeyConstraint, and_, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings
from payroll.const.status import PayrollStatus, PayrollLineSource


class PayrollSettlementModel(Base, TeamScopedMixin):
    """정산 헤더 — 드라이버 × 기간."""
    __tablename__ = "payroll_settlement"

    driver_id: Mapped[int] = mapped_column(ForeignKey("driver.id", ondelete="RESTRICT"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end:   Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PayrollStatus] = mapped_column(
        SAEnum(PayrollStatus, name="payroll_status"),
        default=PayrollStatus.DRAFT, server_default=PayrollStatus.DRAFT.value, nullable=False,
    )
    base_total:        Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    addon_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    grand_total:       Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    lines: Mapped[list["PayrollLineModel"]] = relationship(
        "PayrollLineModel", back_populates="settlement", cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT, order_by="PayrollLineModel.id.asc()",
        primaryjoin=lambda: and_(
            foreign(PayrollLineModel.team_id) == PayrollSettlementModel.team_id,
            foreign(PayrollLineModel.settlement_id) == PayrollSettlementModel.id,
        ),
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_payroll_settlement_team_id_id"),
        Index("ix_payroll_settlement_team_active_id", "team_id", "is_active", "id"),
        Index("ix_payroll_settlement_team_driver", "team_id", "driver_id"),
        Index("ix_payroll_settlement_team_status", "team_id", "status"),
        Index("ix_payroll_settlement_team_period", "team_id", "period_start", "period_end"),
        Index("ix_payroll_settlement_team_updated_at", "team_id", "updated_at"),
    )


class PayrollLineModel(Base, TeamScopedMixin):
    """정산 라인 — leg 1건의 base 요율 snapshot(동결)."""
    __tablename__ = "payroll_line"
    __with_team_rel__ = False

    settlement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    leg_id: Mapped[int | None] = mapped_column(ForeignKey("leg.id", ondelete="SET NULL"), nullable=True)
    work_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    source: Mapped[PayrollLineSource] = mapped_column(
        SAEnum(PayrollLineSource, name="payroll_line_source"),
        default=PayrollLineSource.RESOLVED, server_default=PayrollLineSource.RESOLVED.value, nullable=False,
    )
    rate_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # method/amount/per_unit/qty/multiplier/zone/entry_id
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)  # UNRESOLVED 사유

    settlement: Mapped["PayrollSettlementModel"] = relationship(
        "PayrollSettlementModel", back_populates="lines", lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(PayrollLineModel.team_id) == PayrollSettlementModel.team_id,
            foreign(PayrollLineModel.settlement_id) == PayrollSettlementModel.id,
        ),
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_payroll_line_team_id_id"),
        ForeignKeyConstraint(["team_id", "settlement_id"],
                             ["payroll_settlement.team_id", "payroll_settlement.id"],
                             ondelete="CASCADE", name="fk_payroll_line_settlement_team_id_id"),
        Index("ix_payroll_line_team_id_id", "team_id", "id"),
        Index("ix_payroll_line_team_settlement", "team_id", "settlement_id"),
        Index("ix_payroll_line_team_leg", "team_id", "leg_id"),
    )


class PayrollChargeModel(Base, TeamScopedMixin):
    """정산의 addon 라인 — addon 정의의 값을 snapshot."""
    __tablename__ = "payroll_charge"
    __with_team_rel__ = False

    settlement_id: Mapped[int] = mapped_column(Integer, nullable=False)
    addon_id: Mapped[int | None] = mapped_column(ForeignKey("addon.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    snapshot_unit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1, server_default="1", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_payroll_charge_team_id_id"),
        ForeignKeyConstraint(["team_id", "settlement_id"],
                             ["payroll_settlement.team_id", "payroll_settlement.id"],
                             ondelete="CASCADE", name="fk_payroll_charge_settlement_team_id_id"),
        Index("ix_payroll_charge_team_id_id", "team_id", "id"),
        Index("ix_payroll_charge_team_settlement", "team_id", "settlement_id"),
    )
