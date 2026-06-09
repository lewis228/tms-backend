# src/load_type_template/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import (
    String, Text, JSON, Integer, Boolean,
    Index, UniqueConstraint, ForeignKeyConstraint, and_, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings
from load_type_template.const.status import (
    LoadDirection, TemplateLocationType, TemplateMoveType, TemplateServiceType, TemplateMoveCode,
)


class LoadTypeTemplateModel(Base, TeamScopedMixin):
    """Load Type 템플릿 (헤더) — 선택 시 step 대로 Leg 자동 생성 (컨플루언스 16종).

    is_system=True 는 seed 로 제공되는 기본 템플릿. 사용자는 커스텀 템플릿 추가 가능.
    """
    __tablename__ = "load_type_template"

    code: Mapped[str] = mapped_column(String(48), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    direction: Mapped[LoadDirection] = mapped_column(
        SAEnum(LoadDirection, name="load_type_direction"), nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    steps: Mapped[list["LoadTypeTemplateStepModel"]] = relationship(
        "LoadTypeTemplateStepModel",
        back_populates="template",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="LoadTypeTemplateStepModel.seq.asc()",
        primaryjoin=lambda: and_(
            foreign(LoadTypeTemplateStepModel.team_id) == LoadTypeTemplateModel.team_id,
            foreign(LoadTypeTemplateStepModel.template_id) == LoadTypeTemplateModel.id,
        ),
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_load_type_template_team_id_id"),
        UniqueConstraint("team_id", "code", name="uq_load_type_template_team_code"),
        Index("ix_load_type_template_team_active_id", "team_id", "is_active", "id"),
        Index("ix_load_type_template_team_direction", "team_id", "direction"),
        Index("ix_load_type_template_team_updated_at", "team_id", "updated_at"),
    )


class LoadTypeTemplateStepModel(Base, TeamScopedMixin):
    """템플릿의 Leg 청사진 (라인). from/to None = Any (Bobtail 등)."""
    __tablename__ = "load_type_template_step"
    __with_team_rel__ = False

    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    from_location_type: Mapped[TemplateLocationType | None] = mapped_column(
        SAEnum(TemplateLocationType, name="lt_from_location_type"), nullable=True,
    )
    to_location_type: Mapped[TemplateLocationType | None] = mapped_column(
        SAEnum(TemplateLocationType, name="lt_to_location_type"), nullable=True,
    )
    move_type: Mapped[TemplateMoveType] = mapped_column(
        SAEnum(TemplateMoveType, name="lt_move_type"), nullable=False,
    )
    service_type: Mapped[TemplateServiceType] = mapped_column(
        SAEnum(TemplateServiceType, name="lt_service_type"), nullable=False,
    )
    move_code: Mapped[TemplateMoveCode | None] = mapped_column(
        SAEnum(TemplateMoveCode, name="lt_move_code"), nullable=True,
    )
    flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"chassis_split": true} 등 기본 플래그
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    template: Mapped["LoadTypeTemplateModel"] = relationship(
        "LoadTypeTemplateModel",
        back_populates="steps",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(LoadTypeTemplateStepModel.team_id) == LoadTypeTemplateModel.team_id,
            foreign(LoadTypeTemplateStepModel.template_id) == LoadTypeTemplateModel.id,
        ),
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_lt_template_step_team_id_id"),
        ForeignKeyConstraint(
            ["team_id", "template_id"],
            ["load_type_template.team_id", "load_type_template.id"],
            ondelete="CASCADE",
            name="fk_lt_template_step_template_team_id_id",
        ),
        Index("ix_lt_template_step_team_id_id", "team_id", "id"),
        Index("ix_lt_template_step_team_template", "team_id", "template_id"),
    )
