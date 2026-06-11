# src/addon/model.py
from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Numeric, Integer, Boolean, ForeignKey, ForeignKeyConstraint,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from addon.const.status import AddonCategory, AddonUnit


class AddonModel(Base, TeamScopedMixin):
    """부가요금 타입 마스터 (순수 카탈로그 — 자동가산/수동). 정산 시 이 정의의 값을 snapshot 한다.

    기사별 금액 차등은 라인 테이블 addon_driver_rate 가 담당
    (마스터 = 단위/분류/청구분기 등 '정의', 기사별 행 = '금액'만 override).
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

    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_addon_team_id_id"),
        UniqueConstraint("team_id", "code", name="uq_addon_team_code"),
        Index("ix_addon_team_active_id", "team_id", "is_active", "id"),
        Index("ix_addon_team_category", "team_id", "category"),
        Index("ix_addon_team_updated_at", "team_id", "updated_at"),
    )


class AddonDriverRateModel(Base, TeamScopedMixin):
    """기사별 add-on 금액 override (라인) — 마스터 정의는 그대로, 금액(amount/percent)만 기사별로.

    정산 해석: 마스터(code) 조회 → (addon_id, driver_id) 행 있으면 그 금액, 없으면 마스터 기본값.
    """
    __tablename__ = "addon_driver_rate"
    __with_team_rel__ = False

    addon_id:  Mapped[int] = mapped_column(Integer, nullable=False)
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("driver.id", ondelete="CASCADE"), nullable=False,
    )
    amount:  Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_addon_driver_rate_team_id_id"),
        UniqueConstraint("team_id", "addon_id", "driver_id", name="uq_addon_driver_rate"),
        ForeignKeyConstraint(
            ["team_id", "addon_id"],
            ["addon.team_id", "addon.id"],
            ondelete="CASCADE",
            name="fk_addon_driver_rate_addon_team_id_id",
        ),
        Index("ix_addon_driver_rate_team_id_id", "team_id", "id"),
        Index("ix_addon_driver_rate_team_addon", "team_id", "addon_id"),
        Index("ix_addon_driver_rate_team_driver", "team_id", "driver_id"),
    )
