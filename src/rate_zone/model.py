# src/rate_zone/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Text, JSON, Integer, ForeignKey,
    Index, UniqueConstraint, ForeignKeyConstraint, and_, Enum as SAEnum,
)
from sqlalchemy.orm import foreign

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings
from rate_zone.const.status import ZoneKind


class RateZoneModel(Base, TeamScopedMixin):
    """원자(zip/도시)를 묶는 압축 레이어 Zone (헤더) — Team-Scoped.

    존은 방식이 아니라 "이 원자들은 요율이 같다" 선언 도구.
    **존에는 종류(kind)가 있다**: ZIP존(멤버=zip 만 — '도시로 추가'는 그 도시 zip 전부를
    넣는 확장 단축키) / 도시존(멤버=도시만, CITY 방식 전용). 한 존에 zip·도시 혼합 금지
    (서비스 레벨 검증 ZONE_KIND_MISMATCH). 해석도 kind 로 필터 — ZIP 방식은 ZIP존만,
    CITY 방식은 도시존만 매칭.
    rate_group_id=NULL 이면 팀 공용(글로벌) 존, 값이 있으면 그 그룹 전용 존
    (해석 시 그룹 스코프 존이 글로벌 존보다 우선).
    Zone 은 지도 폴리곤(geojson) 으로 시각화하고, 실제 조회는 원자→zone 인덱스(members)로 한다.
    """
    __tablename__ = "rate_zone"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[ZoneKind] = mapped_column(
        SAEnum(ZoneKind, name="zone_kind"),
        default=ZoneKind.ZIP, server_default=ZoneKind.ZIP.value, nullable=False,
    )
    rate_group_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("rate_group.id", ondelete="CASCADE"),
        nullable=True,  # NULL = 팀 공용 존
    )
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
        Index("ix_rate_zone_team_group",      "team_id", "rate_group_id"),
        Index("ix_rate_zone_team_updated_at",  "team_id", "updated_at"),
    )


class RateZoneMemberModel(Base, TeamScopedMixin):
    """Zone 의 원자 멤버 (라인) — 원자→zone 조회 인덱스의 진실.

    멤버 = zip 1개(ZIP 방식 존) 또는 (city,state) 1개(CITY 방식 도시존).
    행당 zip_code XOR (city,state) — 앱 레벨 검증(서비스/스키마).
    조회는 폴리곤 연산이 아니라 이 테이블 매칭으로 한다. Excel import 로 대량 채운다.
    """
    __tablename__ = "rate_zone_member"
    __with_team_rel__ = False  # .team 은 헤더(zone) 통해 접근

    zone_id:  Mapped[int] = mapped_column(Integer, nullable=False)
    zip_code: Mapped[str | None] = mapped_column(String(16), nullable=True)   # zip 멤버
    city:     Mapped[str | None] = mapped_column(String(120), nullable=True)  # city 멤버 (도시존)
    state:    Mapped[str | None] = mapped_column(String(8), nullable=True)

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
        Index("ix_rate_zone_member_team_city",  "team_id", "city", "state"),
    )
