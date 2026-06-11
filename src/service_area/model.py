# src/service_area/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Index, UniqueConstraint, Enum as SAEnum

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from service_area.const.status import ServiceAreaKind


class ServiceAreaModel(Base, TeamScopedMixin):
    """영업권역(Service Area) 선언 — Team-Scoped.

    설계문서 §8 방어 1: 팀이 "우리가 영업하는 권역"을 선언하면 요율 화면의
    ZIP/도시 자동완성이 그 권역으로 좁혀진다(입력 편의 필터 — 해석/정산과는 무관).
    행 1개 = 선언 1건: (kind, state, value).
    STATE kind 는 value=state 동일값 (uq 의 NULL 회피 — MySQL 유니크는 NULL 을 중복 허용).
    """
    __tablename__ = "service_area"

    kind: Mapped[ServiceAreaKind] = mapped_column(
        SAEnum(ServiceAreaKind, name="service_area_kind"), nullable=False,
    )
    state: Mapped[str] = mapped_column(String(8), nullable=False)    # 2자 주 코드 (예: CA)
    value: Mapped[str] = mapped_column(String(120), nullable=False)  # 카운티/도시명, ZIP3 prefix, STATE=state

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_service_area_team_id_id"),
        UniqueConstraint("team_id", "kind", "state", "value", name="uq_service_area_selection"),
        Index("ix_service_area_team_active_id", "team_id", "is_active", "id"),
        Index("ix_service_area_team_updated_at", "team_id", "updated_at"),
    )
