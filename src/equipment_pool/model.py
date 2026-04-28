# src/equipment_pool/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Text, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from equipment_pool.const.status import EquipmentPoolKind


class EquipmentPoolModel(Base, TeamScopedMixin):
    """챠시 풀 마스터. TERMINAL / THIRD_PARTY (TRAC, FlexiVan, DCLI 등)."""
    __tablename__ = "equipment_pool"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[EquipmentPoolKind] = mapped_column(
        SAEnum(EquipmentPoolKind, name="equipment_pool_kind"),
        nullable=False,
    )
    operator: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )
    contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_equipment_pool_team_id_id"),
        UniqueConstraint("team_id", "name", name="uq_equipment_pool_team_name"),
        Index("ix_equipment_pool_team_kind", "team_id", "kind"),
        Index("ix_equipment_pool_team_active_id", "team_id", "is_active", "id"),
    )
