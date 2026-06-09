# src/driver/model.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Text, Integer, Numeric, Date, DateTime, ForeignKey,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from driver.const.status import EmploymentKind, PaymentTermsKind, DutyStatus


class DriverModel(Base, TeamScopedMixin):
    """기사 (Team-Scoped). User 와 1:1 — User.role=DRIVER. H-3: 트럭 분리. H-5: 고용/정산 확장.

    Mobile (driver app) 추가:
      - duty_status: 근무 상태 토글 (OFF_DUTY / ON_DUTY / IN_BREAK)
      - duty_changed_at: 마지막 토글 시각 (오늘 근무시간 계산용)
    """
    __tablename__ = "driver"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False,
    )
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_state:  Mapped[str | None] = mapped_column(String(8),  nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Mobile 근무 상태 ──────────────────────────────
    duty_status: Mapped[DutyStatus] = mapped_column(
        SAEnum(DutyStatus, name="duty_status"),
        default=DutyStatus.OFF_DUTY,
        server_default=DutyStatus.OFF_DUTY.value,
        nullable=False,
    )
    duty_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── H-5: 고용 형태 + 외부 carrier 소속 ─────────────
    employment_kind: Mapped[EmploymentKind] = mapped_column(
        SAEnum(EmploymentKind, name="employment_kind"),
        default=EmploymentKind.IN_HOUSE,
        server_default=EmploymentKind.IN_HOUSE.value,
        nullable=False,
    )
    # 외부 carrier 소속 시 customer 테이블 (kind=CARRIER) 의 row 를 참조.
    # OWNER_OPERATOR_SOLO 인 프리랜서는 NULL.
    carrier_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 정산 ─────────────────────────────────────────
    payment_terms_kind:  Mapped[PaymentTermsKind | None] = mapped_column(
        SAEnum(PaymentTermsKind, name="payment_terms_kind"), nullable=True,
    )
    payment_terms_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    # ── 기본 자산 (선호 트럭/챠시) ───────────────────
    default_truck_id:   Mapped[int | None] = mapped_column(
        ForeignKey("truck.id", ondelete="SET NULL"), nullable=True,
    )
    default_chassis_id: Mapped[int | None] = mapped_column(
        ForeignKey("chassis.id", ondelete="SET NULL"), nullable=True,
    )

    # ── 컴플라이언스 (DQ — Driver Qualification) ──────────
    license_expires_at:      Mapped[date | None] = mapped_column(Date, nullable=True)
    medical_cert_expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    twic_expires_at:         Mapped[date | None] = mapped_column(Date, nullable=True)
    hire_date:               Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_driver_team_id_id"),
        UniqueConstraint("team_id", "user_id", name="uq_driver_team_user"),
        Index("ix_driver_team_active_id", "team_id", "is_active", "id"),
        Index("ix_driver_team_user", "team_id", "user_id"),
        Index("ix_driver_team_carrier", "team_id", "carrier_id"),
        Index("ix_driver_team_employment", "team_id", "employment_kind"),
        Index("ix_driver_team_updated_at", "team_id", "updated_at"),
    )
