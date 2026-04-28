"""H-4 equipment_pool + chassis + container/leg.chassis_id 정규화

Revision ID: h4chassis0004
Revises: h3truck00003
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4chassis0004"
down_revision: Union[str, None] = "h3truck00003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) equipment_pool ─────────────────────────────────────
    op.create_table(
        "equipment_pool",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("TERMINAL_POOL", "THIRD_PARTY_POOL", name="equipment_pool_kind"),
            nullable=False,
        ),
        sa.Column("operator", sa.String(length=200), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("contact", sa.String(length=200), nullable=True),
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
        sa.ForeignKeyConstraint(["location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_equipment_pool_team_id_id"),
        sa.UniqueConstraint("team_id", "name", name="uq_equipment_pool_team_name"),
    )
    op.create_index("ix_equipment_pool_team_id", "equipment_pool", ["team_id"], unique=False)
    op.create_index("ix_equipment_pool_team_kind", "equipment_pool", ["team_id", "kind"], unique=False)
    op.create_index("ix_equipment_pool_team_active_id", "equipment_pool", ["team_id", "is_active", "id"], unique=False)

    # ── 2) chassis ────────────────────────────────────────────
    op.create_table(
        "chassis",
        sa.Column("chassis_number", sa.String(length=32), nullable=False),
        sa.Column(
            "size",
            sa.Enum("20", "40", "45", "COMBO", name="chassis_size"),
            nullable=True,
        ),
        sa.Column(
            "owner_kind",
            sa.Enum(
                "COMPANY", "DRIVER", "TERMINAL_POOL", "THIRD_PARTY_POOL",
                name="chassis_owner_kind",
            ),
            server_default="COMPANY", nullable=False,
        ),
        sa.Column("owner_driver_id", sa.Integer(), nullable=True),
        sa.Column("owner_pool_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "AVAILABLE", "IN_USE", "AT_POOL", "MAINTENANCE",
                name="chassis_status",
            ),
            server_default="AVAILABLE", nullable=False,
        ),
        sa.Column("current_location_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_pool_id"], ["equipment_pool.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_chassis_team_id_id"),
        sa.UniqueConstraint("team_id", "chassis_number", name="uq_chassis_team_number"),
    )
    op.create_index("ix_chassis_team_id", "chassis", ["team_id"], unique=False)
    op.create_index("ix_chassis_team_owner", "chassis", ["team_id", "owner_kind"], unique=False)
    op.create_index("ix_chassis_team_owner_drv", "chassis", ["team_id", "owner_driver_id"], unique=False)
    op.create_index("ix_chassis_team_owner_pool", "chassis", ["team_id", "owner_pool_id"], unique=False)
    op.create_index("ix_chassis_team_status", "chassis", ["team_id", "status"], unique=False)
    op.create_index("ix_chassis_team_active_id", "chassis", ["team_id", "is_active", "id"], unique=False)

    # ── 3) container.chassis_number → container.chassis_id (FK) ──
    try:
        op.drop_column("container", "chassis_number")
    except Exception:
        pass
    op.add_column("container", sa.Column("chassis_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_container_chassis_id", "container", "chassis",
        ["chassis_id"], ["id"], ondelete="SET NULL",
    )

    # ── 4) leg.chassis_id ─────────────────────────────────────
    op.add_column("leg", sa.Column("chassis_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_leg_chassis_id", "leg", "chassis",
        ["chassis_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_leg_team_chassis", "leg", ["team_id", "chassis_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leg_team_chassis", table_name="leg")
    op.drop_constraint("fk_leg_chassis_id", "leg", type_="foreignkey")
    op.drop_column("leg", "chassis_id")

    op.drop_constraint("fk_container_chassis_id", "container", type_="foreignkey")
    op.drop_column("container", "chassis_id")
    op.add_column("container", sa.Column("chassis_number", sa.String(length=32), nullable=True))

    op.drop_index("ix_chassis_team_active_id", table_name="chassis")
    op.drop_index("ix_chassis_team_status", table_name="chassis")
    op.drop_index("ix_chassis_team_owner_pool", table_name="chassis")
    op.drop_index("ix_chassis_team_owner_drv", table_name="chassis")
    op.drop_index("ix_chassis_team_owner", table_name="chassis")
    op.drop_index("ix_chassis_team_id", table_name="chassis")
    op.drop_table("chassis")

    op.drop_index("ix_equipment_pool_team_active_id", table_name="equipment_pool")
    op.drop_index("ix_equipment_pool_team_kind", table_name="equipment_pool")
    op.drop_index("ix_equipment_pool_team_id", table_name="equipment_pool")
    op.drop_table("equipment_pool")
