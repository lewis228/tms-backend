# src/chassis/model.py
from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Text, Date, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from chassis.const.status import ChassisOwnerKind, ChassisSize, ChassisStatus


class ChassisModel(Base, TeamScopedMixin):
    """챠시 마스터. owner_kind: COMPANY/DRIVER/TERMINAL_POOL/THIRD_PARTY_POOL."""
    __tablename__ = "chassis"

    chassis_number: Mapped[str] = mapped_column(String(32), nullable=False)
    # ChassisSize.value 가 "20"/"40" 등 (식별자 시작문자 제약 회피용 name 사용).
    # SQLAlchemy 가 .name 대신 .value 를 저장하도록 values_callable 명시.
    size: Mapped[ChassisSize | None] = mapped_column(
        SAEnum(
            ChassisSize, name="chassis_size",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )

    owner_kind: Mapped[ChassisOwnerKind] = mapped_column(
        SAEnum(ChassisOwnerKind, name="chassis_owner_kind"),
        default=ChassisOwnerKind.COMPANY,
        server_default=ChassisOwnerKind.COMPANY.value,
        nullable=False,
    )
    owner_driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("driver.id", ondelete="SET NULL"), nullable=True,
    )
    owner_pool_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipment_pool.id", ondelete="SET NULL"), nullable=True,
    )

    status: Mapped[ChassisStatus] = mapped_column(
        SAEnum(ChassisStatus, name="chassis_status"),
        default=ChassisStatus.AVAILABLE,
        server_default=ChassisStatus.AVAILABLE.value,
        nullable=False,
    )
    current_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("location.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 장비 만료 추적 (Phase 6 만료 알림) ───────────────────────
    registration_expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspection_expires_at:   Mapped[date | None] = mapped_column(Date, nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_chassis_team_id_id"),
        UniqueConstraint("team_id", "chassis_number", name="uq_chassis_team_number"),
        Index("ix_chassis_team_owner",     "team_id", "owner_kind"),
        Index("ix_chassis_team_owner_drv", "team_id", "owner_driver_id"),
        Index("ix_chassis_team_owner_pool", "team_id", "owner_pool_id"),
        Index("ix_chassis_team_status",    "team_id", "status"),
        Index("ix_chassis_team_active_id", "team_id", "is_active", "id"),
    )
