# src/rate_zone/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Text, JSON, Integer,
    Index, UniqueConstraint, ForeignKeyConstraint, and_,
)
from sqlalchemy.orm import foreign

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings


class RateZoneModel(Base, TeamScopedMixin):
    """요율표의 '열'이 되는 Zone (헤더) — Team-Scoped.

    컨플루언스 [Terry] 요율표 기획: 고객사가 위치한 지리적 구역(Zone)이 Rate Sheet 의 열.
    Zone 은 지도 폴리곤(geojson) 으로 시각화하고, 실제 조회는 zip→zone 인덱스(members)로 한다.
    """
    __tablename__ = "rate_zone"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)        # 지도 표시색 (#RRGGBB)
    geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)           # 폴리곤(시각화/백필 전용)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    members: Mapped[list["RateZoneMemberModel"]] = relationship(
        "RateZoneMemberModel",
        back_populates="zone",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="RateZoneMemberModel.id.asc()",
        primaryjoin=lambda: and_(
            foreign(RateZoneMemberModel.team_id) == RateZoneModel.team_id,
            foreign(RateZoneMemberModel.zone_id) == RateZoneModel.id,
        ),
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_zone_team_id_id"),
        UniqueConstraint("team_id", "name", name="uq_rate_zone_team_name"),
        Index("ix_rate_zone_team_active_id", "team_id", "is_active", "id"),
        Index("ix_rate_zone_team_name",       "team_id", "name"),
        Index("ix_rate_zone_team_updated_at",  "team_id", "updated_at"),
    )


class RateZoneMemberModel(Base, TeamScopedMixin):
    """Zone 의 zip 멤버 (라인) — zip→zone 조회 인덱스의 진실.

    조회는 폴리곤 연산이 아니라 이 테이블의 zip_code 매칭으로 한다.
    (존 = zip 묶음. 도시별 요율은 CITY 방식의 rate_entry.col_city 가 별도 담당.)
    Excel import 로 대량 채운다.
    """
    __tablename__ = "rate_zone_member"
    __with_team_rel__ = False  # .team 은 헤더(zone) 통해 접근

    zone_id:  Mapped[int] = mapped_column(Integer, nullable=False)
    zip_code: Mapped[str] = mapped_column(String(16), nullable=False)  # 존 멤버 유일 키(zip 묶음)

    zone: Mapped["RateZoneModel"] = relationship(
        "RateZoneModel",
        back_populates="members",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(RateZoneMemberModel.team_id) == RateZoneModel.team_id,
            foreign(RateZoneMemberModel.zone_id) == RateZoneModel.id,
        ),
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_rate_zone_member_team_id_id"),
        ForeignKeyConstraint(
            ["team_id", "zone_id"],
            ["rate_zone.team_id", "rate_zone.id"],
            ondelete="CASCADE",
            name="fk_rate_zone_member_zone_team_id_id",
        ),
        Index("ix_rate_zone_member_team_id_id", "team_id", "id"),
        Index("ix_rate_zone_member_team_zone",  "team_id", "zone_id"),
        Index("ix_rate_zone_member_team_zip",   "team_id", "zip_code"),
    )
