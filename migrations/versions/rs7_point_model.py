"""point model — container_stop role→point_type(+terminal/customer), leg from/to_point

포인트 모델 전면 재설계 Phase 1:
- container_stop: role(StopRole) 제거 → point_type(PointType TERMINAL/YARD/CUSTOMER)
  + terminal_id/customer_id 추가(타입별 마스터 참조).
- leg: pickup_location_id/delivery_location_id 제거 → from_point_id/to_point_id
  (container_stop 참조) 추가. from/to_location_type 컬럼은 그대로(스냅샷).
기존 데이터는 폐기 가능 — point_type 은 일괄 YARD 로 백필.

Revision ID: rs7_point_model
Revises: rs6_drop_ce_so
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs7_point_model'
down_revision: Union[str, None] = 'rs6_drop_ce_so'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POINT_ENUM = sa.Enum("TERMINAL", "YARD", "CUSTOMER", name="point_type")


def upgrade() -> None:
    # ── container_stop: role → point_type + terminal_id/customer_id ──
    op.drop_index("ix_container_stop_team_role", table_name="container_stop")
    op.drop_column("container_stop", "role")
    op.add_column("container_stop", sa.Column(
        "point_type", _POINT_ENUM, nullable=False, server_default="YARD",
    ))
    op.alter_column("container_stop", "point_type",
                    existing_type=_POINT_ENUM, server_default=None, existing_nullable=False)
    op.add_column("container_stop", sa.Column("terminal_id", sa.Integer(), nullable=True))
    op.add_column("container_stop", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_container_stop_terminal", "container_stop", "terminal",
        ["terminal_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_container_stop_customer", "container_stop", "customer",
        ["customer_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_container_stop_team_type", "container_stop", ["team_id", "point_type"])

    # ── leg: pickup/delivery_location → from_point/to_point ──
    op.drop_constraint("leg_ibfk_5", "leg", type_="foreignkey")  # pickup_location_id
    op.drop_constraint("leg_ibfk_2", "leg", type_="foreignkey")  # delivery_location_id
    op.drop_index("pickup_location_id", table_name="leg")
    op.drop_index("delivery_location_id", table_name="leg")
    op.drop_column("leg", "pickup_location_id")
    op.drop_column("leg", "delivery_location_id")
    op.add_column("leg", sa.Column("from_point_id", sa.Integer(), nullable=True))
    op.add_column("leg", sa.Column("to_point_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_leg_from_point", "leg", "container_stop",
        ["from_point_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_leg_to_point", "leg", "container_stop",
        ["to_point_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_leg_team_from_point", "leg", ["team_id", "from_point_id"])
    op.create_index("ix_leg_team_to_point", "leg", ["team_id", "to_point_id"])


def downgrade() -> None:
    # leg
    op.drop_index("ix_leg_team_to_point", table_name="leg")
    op.drop_index("ix_leg_team_from_point", table_name="leg")
    op.drop_constraint("fk_leg_to_point", "leg", type_="foreignkey")
    op.drop_constraint("fk_leg_from_point", "leg", type_="foreignkey")
    op.drop_column("leg", "to_point_id")
    op.drop_column("leg", "from_point_id")
    op.add_column("leg", sa.Column("pickup_location_id", sa.Integer(), nullable=True))
    op.add_column("leg", sa.Column("delivery_location_id", sa.Integer(), nullable=True))
    op.create_foreign_key("leg_ibfk_5", "leg", "location", ["pickup_location_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("leg_ibfk_2", "leg", "location", ["delivery_location_id"], ["id"], ondelete="SET NULL")
    op.create_index("pickup_location_id", "leg", ["pickup_location_id"])
    op.create_index("delivery_location_id", "leg", ["delivery_location_id"])

    # container_stop
    op.drop_index("ix_container_stop_team_type", table_name="container_stop")
    op.drop_constraint("fk_container_stop_customer", "container_stop", type_="foreignkey")
    op.drop_constraint("fk_container_stop_terminal", "container_stop", type_="foreignkey")
    op.drop_column("container_stop", "customer_id")
    op.drop_column("container_stop", "terminal_id")
    op.drop_column("container_stop", "point_type")
    op.add_column("container_stop", sa.Column(
        "role", sa.Enum("ORIGIN", "DELIVERY", "TRANSIT", "TERMINUS", name="stop_role"),
        nullable=False, server_default="TRANSIT",
    ))
    op.alter_column("container_stop", "role",
                    existing_type=sa.Enum("ORIGIN", "DELIVERY", "TRANSIT", "TERMINUS", name="stop_role"),
                    server_default=None, existing_nullable=False)
    op.create_index("ix_container_stop_team_role", "container_stop", ["team_id", "role"])
