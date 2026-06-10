"""drop leg_charge_event / leg_stop_off (Layer 3 폐기 → add-on 통합)

컨플루언스 재정의(2026-06-10): Layer 1/2/3 구분 폐기. 옛 Layer 3 Charge Event 와
경유지(Stop Off) 는 모두 leg_addon 한 테이블(중복 허용)로 흡수됐다. 두 dead 테이블 제거.

Revision ID: rs6_drop_ce_so
Revises: rs5_drop_legacy_leg
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs6_drop_ce_so'
down_revision: Union[str, None] = 'rs5_drop_legacy_leg'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("leg_charge_event")
    op.drop_table("leg_stop_off")


def downgrade() -> None:
    op.create_table(
        "leg_charge_event",
        sa.Column("leg_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.Enum("DET", "DMR", "YRD", "STP", name="leg_charge_event_code"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("free_minutes", sa.Integer(), nullable=True),
        sa.Column("free_days", sa.Integer(), nullable=True),
        sa.Column("actual_minutes", sa.Integer(), nullable=True),
        sa.Column("actual_days", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["team_id", "leg_id"], ["leg.team_id", "leg.id"],
            ondelete="CASCADE", name="fk_leg_charge_event_leg_team_id_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_leg_charge_event_team_id_id"),
        sa.UniqueConstraint("team_id", "leg_id", "code", name="uq_leg_charge_event_leg_code"),
    )
    op.create_index("ix_leg_charge_event_team_id_id", "leg_charge_event", ["team_id", "id"])
    op.create_index("ix_leg_charge_event_team_leg", "leg_charge_event", ["team_id", "leg_id"])

    op.create_table(
        "leg_stop_off",
        sa.Column("leg_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("pod_file_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pod_file_id"], ["file_asset.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["team_id", "leg_id"], ["leg.team_id", "leg.id"],
            ondelete="CASCADE", name="fk_leg_stop_off_leg_team_id_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_leg_stop_off_team_id_id"),
    )
    op.create_index("ix_leg_stop_off_team_id_id", "leg_stop_off", ["team_id", "id"])
    op.create_index("ix_leg_stop_off_team_leg", "leg_stop_off", ["team_id", "leg_id"])
