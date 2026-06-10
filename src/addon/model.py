# src/addon/model.py
from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Numeric, Integer, Boolean, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from addon.const.status import AddonCategory, AddonUnit


class AddonModel(Base, TeamScopedMixin):
    """부가요금 규칙 마스터 (자동가산/수동). 정산 시 이 정의의 값을 snapshot 한다.

    driver_id 가 있으면 그 드라이버 전용 override(예: 드라이버별 Fuel %).
    driver_id NULL = 팀 전역 기본.
    """
    __tablename__ = "addon"

    code: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[AddonCategory] = mapped_column(
        SAEnum(AddonCategory, name="addon_category"), nullable=False,
    )
    unit: Mapped[AddonUnit] = mapped_column(
        SAEnum(AddonUnit, name="addon_unit"), nullable=False,
    )

    amount:  Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)   # FLAT/HOUR/MINUTE/DAY/MILE
    percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)    # PERCENT(FUEL 등)
    free_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)         # WAITING 무료시간
    free_days:    Mapped[int | None] = mapped_column(Integer, nullable=True)         # PENALTY 무료일수

    auto_apply: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    is_system:  Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    # 청구/정산 분기 (독립 스위치): 고객 청구 대상 / 기사 지급 대상
    is_billable_to_customer: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    is_payable_to_driver:    Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)

    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="CASCADE"), nullable=True,  # per-driver override
    )
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_addon_team_id_id"),
        UniqueConstraint("team_id", "code", "driver_id", name="uq_addon_code_driver"),
        Index("ix_addon_team_active_id", "team_id", "is_active", "id"),
        Index("ix_addon_team_category", "team_id", "category"),
        Index("ix_addon_team_code", "team_id", "code"),
        Index("ix_addon_team_driver", "team_id", "driver_id"),
        Index("ix_addon_team_updated_at", "team_id", "updated_at"),
    )
