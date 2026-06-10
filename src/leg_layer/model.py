# src/leg_layer/model.py
"""Leg Add-on 라인 테이블 — 기존 leg 에 additive.

컨플루언스 재정의(2026-06-10): Layer 1/2/3 구분 폐기. 옛 Add-on(Layer2) + 옛
Charge Event(Layer3) + 경유지(Stop Off) 를 모두 **leg_addon 한 테이블**(중복 가능)로 통합.

leg(team_id, id) 복합 FK. leg 본체 재설계와 무관하게 leg PK 만 유지되면 호환.
"""
from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, JSON, Numeric, Boolean, ForeignKey,
    Index, UniqueConstraint, ForeignKeyConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from leg.const.status import PointType


class LegAddonModel(Base, TeamScopedMixin):
    """Leg 의 Add-on 인스턴스(=레그에 붙인 부가요금 한 줄). 한 레그에 여러 행 가능(Stop Off ×3 등).

    **addon_id** = 어떤 addon 타입(마스터)인지. code = addon.code 스냅샷(표시/청구). amount = 확정 금액
    (추가 시 addon 마스터 단가로 자동 채움 + 사용자 수정).

    addon.category==EXTRA_STOP(Stop Off) 인 경우만 typed 위치(point_type + terminal_id/location_id/
    customer_id, 정확히 하나)를 채운다 — '그 레그에서 추가로 들른 곳'. 나머지 타입은 NULL.
    """
    __tablename__ = "leg_addon"
    __with_team_rel__ = False

    leg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    addon_id: Mapped[int | None] = mapped_column(ForeignKey("addon.id", ondelete="SET NULL"), nullable=True)
    code: Mapped[str] = mapped_column(String(48), nullable=False)  # addon.code 스냅샷
    quantity:    Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1, server_default="1", nullable=False)
    unit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount:      Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    amount_override: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)  # 레거시
    # ── 청구/정산 분기 플래그 (addon 마스터에서 부착 시점 스냅샷) ──
    # 독립 스위치: 정산만/청구만/둘다/둘다아님. 정산은 payable, 청구는 billable 인 것만 합산.
    is_payable_to_driver:    Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    is_billable_to_customer: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    # ── typed 위치 (STP 등에서만 채움, 나머지 code 는 null) ──
    point_type: Mapped[PointType | None] = mapped_column(
        SAEnum(PointType, name="leg_addon_point_type"), nullable=True,
    )
    terminal_id: Mapped[int | None] = mapped_column(ForeignKey("terminal.id", ondelete="SET NULL"), nullable=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("location.id", ondelete="SET NULL"), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customer.id", ondelete="SET NULL"), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_leg_addon_team_id_id"),
        ForeignKeyConstraint(["team_id", "leg_id"], ["leg.team_id", "leg.id"],
                             ondelete="CASCADE", name="fk_leg_addon_leg_team_id_id"),
        Index("ix_leg_addon_team_id_id", "team_id", "id"),
        Index("ix_leg_addon_team_leg", "team_id", "leg_id"),
        Index("ix_leg_addon_team_addon", "team_id", "addon_id"),
    )
