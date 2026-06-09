# src/dual_transaction/model.py
"""Dual Transaction (재설계 Phase 4) — 반납 leg + 픽업 leg 를 한 드라이버 한 트립으로 묶음.

빈 컨테이너 반납 leg 와 다른 컨테이너 픽업 leg 를 한 드라이버가 연속 수행해 공차를 줄인다.
두 leg 는 보통 서로 다른 D/O/컨테이너에 속한다. 묶음 자체는 단일 헤더(라인 없음).
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from dual_transaction.const.status import DualTransactionStatus


class DualTransactionModel(Base, TeamScopedMixin):
    __tablename__ = "dual_transaction"

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("driver.id", ondelete="RESTRICT"), nullable=False,
    )
    truck_id: Mapped[int | None] = mapped_column(
        ForeignKey("truck.id", ondelete="SET NULL"), nullable=True,
    )
    # 묶이는 두 leg — leg 하드삭제 시 묶음도 정리(CASCADE)
    return_leg_id: Mapped[int] = mapped_column(
        ForeignKey("leg.id", ondelete="CASCADE"), nullable=False,
    )
    pickup_leg_id: Mapped[int] = mapped_column(
        ForeignKey("leg.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[DualTransactionStatus] = mapped_column(
        SAEnum(DualTransactionStatus, name="dual_transaction_status"),
        default=DualTransactionStatus.PLANNED,
        server_default=DualTransactionStatus.PLANNED.value,
        nullable=False,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_dual_transaction_team_id_id"),
        Index("ix_dual_transaction_team_active_id", "team_id", "is_active", "id"),
        Index("ix_dual_transaction_team_driver", "team_id", "driver_id"),
        Index("ix_dual_transaction_team_status", "team_id", "status"),
        Index("ix_dual_transaction_team_return_leg", "team_id", "return_leg_id"),
        Index("ix_dual_transaction_team_pickup_leg", "team_id", "pickup_leg_id"),
        Index("ix_dual_transaction_team_updated_at", "team_id", "updated_at"),
    )
