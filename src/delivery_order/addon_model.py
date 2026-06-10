# src/delivery_order/addon_model.py
"""D/O 단위 Add-on (고객 청구용) — Demurrage/Detention/Hazmat 등.

컨플루언스 재정의: leg 가 아니라 그 건(D/O) 전체에 붙는 추가요금. 고객 청구(invoice)에 자동 가산.
leg add-on(leg_addon)과 별개 — 부착 위치(leg vs D/O)가 곧 청구 단위.
"""
from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Numeric, JSON, ForeignKey,
    Index, UniqueConstraint, ForeignKeyConstraint,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class DeliveryOrderAddonModel(Base, TeamScopedMixin):
    """D/O 단위 추가요금 인스턴스 (중복 가능). addon_id=타입, code=addon.code 스냅샷, amount=확정."""
    __tablename__ = "delivery_order_addon"
    __with_team_rel__ = False

    delivery_order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    addon_id: Mapped[int | None] = mapped_column(ForeignKey("addon.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False)  # addon.code 스냅샷
    quantity:    Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1, server_default="1", nullable=False)
    unit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount:      Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_do_addon_team_id_id"),
        ForeignKeyConstraint(["team_id", "delivery_order_id"],
                             ["delivery_order.team_id", "delivery_order.id"],
                             ondelete="CASCADE", name="fk_do_addon_do_team_id_id"),
        Index("ix_do_addon_team_id_id", "team_id", "id"),
        Index("ix_do_addon_team_do", "team_id", "delivery_order_id"),
    )
