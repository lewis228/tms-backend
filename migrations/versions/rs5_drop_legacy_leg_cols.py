"""drop legacy leg columns (leg_kind / move_type_v3 / from_stop_id / to_stop_id)

재설계(컨플루언스 "Leg 전체 유형") 이후 leg 는 (from/to_location_type, move_type,
service_type, move_code) 로 표현된다. v3 시절의 leg_kind / move_type_v3 4축 형상 /
container_stop 기반 from_stop_id·to_stop_id 는 더 이상 세팅·조회되지 않는 dead 컬럼이라 제거.

Revision ID: rs5_drop_legacy_leg
Revises: rs4_do_addon
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs5_drop_legacy_leg'
down_revision: Union[str, None] = 'rs4_do_addon'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) container_stop 참조 FK 제거 (인덱스보다 먼저)
    op.drop_constraint("leg_ibfk_8", "leg", type_="foreignkey")
    op.drop_constraint("leg_ibfk_9", "leg", type_="foreignkey")

    # 2) FK 가 만든 인덱스 + leg_kind 인덱스 제거
    op.drop_index("from_stop_id", table_name="leg")
    op.drop_index("to_stop_id", table_name="leg")
    op.drop_index("ix_leg_team_kind", table_name="leg")

    # 3) dead 컬럼 제거 (MySQL: 인라인 enum 타입도 함께 사라짐)
    op.drop_column("leg", "from_stop_id")
    op.drop_column("leg", "to_stop_id")
    op.drop_column("leg", "move_type_v3")
    op.drop_column("leg", "leg_kind")


def downgrade() -> None:
    op.add_column("leg", sa.Column(
        "leg_kind",
        sa.Enum(
            "BOBTAIL", "PICKUP", "DROP", "LIVE_UNLOAD", "RETURN", "STREET_TURN",
            "CHASSIS_FLIP", "DRY_RUN", "REPOSITION", "PARTIAL_PICKUP", "MULTI_STOP_DELIVERY",
            name="leg_kind",
        ),
        nullable=True,
    ))
    op.add_column("leg", sa.Column(
        "move_type_v3",
        sa.Enum("TRUCK_ONLY", "CHASSIS_ONLY", "EMPTY_LOADED", "FULL_LOADED", name="move_type_v3"),
        nullable=True,
    ))
    op.add_column("leg", sa.Column("to_stop_id", sa.Integer(), nullable=True))
    op.add_column("leg", sa.Column("from_stop_id", sa.Integer(), nullable=True))

    op.create_index("ix_leg_team_kind", "leg", ["team_id", "leg_kind"], unique=False)
    op.create_index("from_stop_id", "leg", ["from_stop_id"], unique=False)
    op.create_index("to_stop_id", "leg", ["to_stop_id"], unique=False)
    op.create_foreign_key(
        "leg_ibfk_8", "leg", "container_stop", ["from_stop_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "leg_ibfk_9", "leg", "container_stop", ["to_stop_id"], ["id"], ondelete="SET NULL",
    )
