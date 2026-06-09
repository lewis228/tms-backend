# src/rate_multiplier/model.py
from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Numeric, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from rate_sheet.const.status import RateContainerSize


class RateMultiplierModel(Base, TeamScopedMixin):
    """컨테이너 타입 배율 (Load/Empty 매트릭스 요율에만 적용, Bobtail 제외).

    컨플루언스: 40ft 기준, 20ft×0.85 / 45ft×1.0 (기본). 셀 override 는 rate_entry 에 직접 입력.
    scope: rate_group_id NULL = 팀 전역 기본, 값 있으면 그 그룹 전용 override.
    """
    __tablename__ = "rate_multiplier"

    rate_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("rate_group.id", ondelete="CASCADE"), nullable=True,  # NULL=팀 전역
    )
    container_size: Mapped[RateContainerSize] = mapped_column(
        SAEnum(RateContainerSize, name="rate_multiplier_container_size"), nullable=False,
    )
    factor: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_multiplier_team_id_id"),
        UniqueConstraint("team_id", "rate_group_id", "container_size", name="uq_rate_multiplier_scope_size"),
        Index("ix_rate_multiplier_team_active", "team_id", "is_active"),
        Index("ix_rate_multiplier_team_group", "team_id", "rate_group_id"),
    )
