"""drop leg_stop (+ chassis_event.leg_stop_id) + leg_addon typed 위치

포인트 모델 Phase 2:
- leg_stop(DEPRECATED 죽은 테이블) 제거. chassis_event.leg_stop_id FK·컬럼도 함께 제거.
- leg_addon 에 typed 위치(point_type + terminal_id/location_id/customer_id) 추가 — Stop(STP) 등
  '그 레그에서 추가로 들른 곳' 표현용.

Revision ID: rs8_leg_stop_addon
Revises: rs7_point_model
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs8_leg_stop_addon'
down_revision: Union[str, None] = 'rs7_point_model'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ADDON_POINT_ENUM = sa.Enum("TERMINAL", "YARD", "CUSTOMER", name="leg_addon_point_type")


def upgrade() -> None:
    # 1) chassis_event.leg_stop_id 제거 (leg_stop 참조 끊기)
    op.drop_constraint("chassis_event_ibfk_5", "chassis_event", type_="foreignkey")
    op.drop_index("leg_stop_id", table_name="chassis_event")
    op.drop_column("chassis_event", "leg_stop_id")

    # 2) leg_stop 테이블 제거
    op.drop_table("leg_stop")

    # 3) leg_addon typed 위치 추가
    op.add_column("leg_addon", sa.Column("point_type", _ADDON_POINT_ENUM, nullable=True))
    op.add_column("leg_addon", sa.Column("terminal_id", sa.Integer(), nullable=True))
    op.add_column("leg_addon", sa.Column("location_id", sa.Integer(), nullable=True))
    op.add_column("leg_addon", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_leg_addon_terminal", "leg_addon", "terminal", ["terminal_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_leg_addon_location", "leg_addon", "location", ["location_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_leg_addon_customer", "leg_addon", "customer", ["customer_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_leg_addon_customer", "leg_addon", type_="foreignkey")
    op.drop_constraint("fk_leg_addon_location", "leg_addon", type_="foreignkey")
    op.drop_constraint("fk_leg_addon_terminal", "leg_addon", type_="foreignkey")
    op.drop_column("leg_addon", "customer_id")
    op.drop_column("leg_addon", "location_id")
    op.drop_column("leg_addon", "terminal_id")
    op.drop_column("leg_addon", "point_type")

    op.create_table(
        "leg_stop",
        sa.Column("leg_id", sa.Integer(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("stop_kind", sa.Enum(
            "PICKUP_FULL", "DROP_FULL", "PICKUP_EMPTY", "DROP_EMPTY", "CHASSIS_GET",
            "CHASSIS_RETURN", "WAIT", "FUEL", "SCALE", "OTHER", name="stop_kind"), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("container_id", sa.Integer(), nullable=True),
        sa.Column("chassis_id", sa.Integer(), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_leg_stop_team_id_id"),
    )
    op.add_column("chassis_event", sa.Column("leg_stop_id", sa.Integer(), nullable=True))
    op.create_index("leg_stop_id", "chassis_event", ["leg_stop_id"])
    op.create_foreign_key("chassis_event_ibfk_5", "chassis_event", "leg_stop", ["leg_stop_id"], ["id"], ondelete="SET NULL")
