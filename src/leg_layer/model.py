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
    String, Integer, JSON, Numeric, ForeignKey,
    Index, UniqueConstraint, ForeignKeyConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from leg_layer.const.status import LegAddonCode
from leg.const.status import PointType


class LegAddonModel(Base, TeamScopedMixin):
    """Leg 의 Add-on(=추가요금 한 줄). 컨플루언스 재정의: Flag/Charge Event 구분 없이 모두 Add-on.

    같은 code 를 여러 개 붙일 수 있다(예: Stop Off ×3). 시스템 자동 추가 + 사용자 CRUD.
    amount 가 이 add-on 의 확정 금액(자동 채움 + 사용자 수정). quantity×unit_amount 내역.

    Stop(STP) 등 '위치가 의미 있는' add-on 은 typed 위치를 가진다(메인 포인트 시퀀스와 별개,
    '그 레그에서 추가로 들른 곳'): point_type + terminal_id/location_id/customer_id(정확히 하나).
    """
    __tablename__ = "leg_addon"
    __with_team_rel__ = False

    leg_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[LegAddonCode] = mapped_column(SAEnum(LegAddonCode, name="leg_addon_code"), nullable=False)
    quantity:    Mapped[Decimal] = mapped_column(Numeric(12, 2), default=1, server_default="1", nullable=False)
    unit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount:      Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    amount_override: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)  # 레거시
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
    )
