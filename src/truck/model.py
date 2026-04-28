# src/truck/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Text, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from truck.const.status import TruckOwnerKind, TruckStatus


class TruckModel(Base, TeamScopedMixin):
    """트럭 (Tractor) 마스터. owner_kind: COMPANY / DRIVER."""
    __tablename__ = "truck"

    plate_no: Mapped[str] = mapped_column(String(32), nullable=False)
    vin:      Mapped[str | None] = mapped_column(String(32), nullable=True)
    make:     Mapped[str | None] = mapped_column(String(64), nullable=True)
    model:    Mapped[str | None] = mapped_column(String(64), nullable=True)
    year:     Mapped[int | None] = mapped_column(Integer, nullable=True)

    owner_kind: Mapped[TruckOwnerKind] = mapped_column(
        SAEnum(TruckOwnerKind, name="truck_owner_kind"),
        default=TruckOwnerKind.COMPANY,
        server_default=TruckOwnerKind.COMPANY.value,
        nullable=False,
    )
    # owner_kind=DRIVER 일 때 채움. ON DELETE SET NULL — 기사 삭제되어도 트럭 row 보존.
    owner_driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="SET NULL"), nullable=True,
    )

    status: Mapped[TruckStatus] = mapped_column(
        SAEnum(TruckStatus, name="truck_status"),
        default=TruckStatus.ACTIVE,
        server_default=TruckStatus.ACTIVE.value,
        nullable=False,
    )

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_truck_team_id_id"),
        UniqueConstraint("team_id", "plate_no", name="uq_truck_team_plate"),
        Index("ix_truck_team_owner",     "team_id", "owner_kind"),
        Index("ix_truck_team_owner_drv", "team_id", "owner_driver_id"),
        Index("ix_truck_team_status",    "team_id", "status"),
        Index("ix_truck_team_active_id", "team_id", "is_active", "id"),
    )
