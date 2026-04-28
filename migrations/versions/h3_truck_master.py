"""H-3 truck master + driver.truck_number drop + leg.truck_id

Revision ID: h3truck00003
Revises: h2charge0002
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h3truck00003"
down_revision: Union[str, None] = "h2charge0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) truck 테이블 (driver FK 참조 가능하도록 driver 다음 단계에서 생성) ──
    op.create_table(
        "truck",
        sa.Column("plate_no", sa.String(length=32), nullable=False),
        sa.Column("vin", sa.String(length=32), nullable=True),
        sa.Column("make", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column(
            "owner_kind",
            sa.Enum("COMPANY", "DRIVER", name="truck_owner_kind"),
            server_default="COMPANY", nullable=False,
        ),
        sa.Column("owner_driver_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "MAINTENANCE", "RETIRED", name="truck_status"),
            server_default="ACTIVE", nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_driver_id"], ["driver.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_truck_team_id_id"),
        sa.UniqueConstraint("team_id", "plate_no", name="uq_truck_team_plate"),
    )
    op.create_index("ix_truck_team_id", "truck", ["team_id"], unique=False)
    op.create_index("ix_truck_team_owner", "truck", ["team_id", "owner_kind"], unique=False)
    op.create_index("ix_truck_team_owner_drv", "truck", ["team_id", "owner_driver_id"], unique=False)
    op.create_index("ix_truck_team_status", "truck", ["team_id", "status"], unique=False)
    op.create_index("ix_truck_team_active_id", "truck", ["team_id", "is_active", "id"], unique=False)

    # ── 2) leg.truck_id 추가 ─────────────────────────────────────
    op.add_column("leg", sa.Column("truck_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_leg_truck_id", "leg", "truck",
        ["truck_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_leg_team_truck", "leg", ["team_id", "truck_id"], unique=False)

    # ── 3) driver.truck_number 제거 ──────────────────────────────
    # init_schema 에서 만들어진 unique 제약 (uq_driver_team_truck) 부터 제거.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    uniques = inspector.get_unique_constraints("driver")
    for uc in uniques:
        if "truck_number" in (uc.get("column_names") or []):
            name = uc.get("name")
            if name:
                try:
                    op.drop_constraint(name, "driver", type_="unique")
                except Exception:
                    pass
    indexes = inspector.get_indexes("driver")
    for idx in indexes:
        if "truck_number" in (idx.get("column_names") or []):
            name = idx.get("name")
            if name:
                try:
                    op.drop_index(name, table_name="driver")
                except Exception:
                    pass
    try:
        op.drop_column("driver", "truck_number")
    except Exception:
        pass


def downgrade() -> None:
    # driver.truck_number 복원
    op.add_column("driver", sa.Column("truck_number", sa.String(length=32), nullable=True))

    op.drop_index("ix_leg_team_truck", table_name="leg")
    op.drop_constraint("fk_leg_truck_id", "leg", type_="foreignkey")
    op.drop_column("leg", "truck_id")

    op.drop_index("ix_truck_team_active_id", table_name="truck")
    op.drop_index("ix_truck_team_status", table_name="truck")
    op.drop_index("ix_truck_team_owner_drv", table_name="truck")
    op.drop_index("ix_truck_team_owner", table_name="truck")
    op.drop_index("ix_truck_team_id", table_name="truck")
    op.drop_table("truck")
