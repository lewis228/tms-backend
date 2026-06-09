# src/audit_log/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, JSON, Index, UniqueConstraint

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class AuditLogModel(Base, TeamScopedMixin):
    """활동 타임라인 / 감사 로그 — append-only. 모든 도메인 공용(폴리모픽).

    entity_type + entity_id 로 대상을 가리키고, action/summary 로 무슨 일이 있었는지 기록.
    before_state/after_state 로 변경 전후 스냅샷(선택). actor 는 created_by_user_id.
    """
    __tablename__ = "audit_log"

    entity_type: Mapped[str] = mapped_column(String(48), nullable=False)   # "delivery_order" / "leg" / "settlement" ...
    entity_id:   Mapped[int] = mapped_column(Integer, nullable=False)
    action:      Mapped[str] = mapped_column(String(64), nullable=False)   # "created" / "status_changed" / "leg_assigned" ...
    summary:     Mapped[str | None] = mapped_column(String(500), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state:  Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_audit_log_team_id_id"),
        Index("ix_audit_log_team_entity", "team_id", "entity_type", "entity_id", "id"),
        Index("ix_audit_log_team_created", "team_id", "created_at"),
    )
