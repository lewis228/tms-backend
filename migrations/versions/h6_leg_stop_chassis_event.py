"""H-6 leg 확장 + leg_stop + chassis_event

Revision ID: h6stop00006
Revises: h5partner00005
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h6stop00006"
down_revision: Union[str, None] = "h5partner00005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) leg.leg_kind / chassis_at_start/end / container_at_start/end / remarks ──
    op.add_column(
        "leg",
        sa.Column(
            "leg_kind",
            sa.Enum(
                "BOBTAIL", "PICKUP", "DROP", "LIVE_UNLOAD", "RETURN",
                "STREET_TURN", "CHASSIS_FLIP", "DRY_RUN", "REPOSITION",
                "PARTIAL_PICKUP", "MULTI_STOP_DELIVERY",
                name="leg_kind",
            ),
            nullable=True,
        ),
    )
    op.add_column("leg", sa.Column("chassis_at_start_id", sa.Integer(), nullable=True))
    op.add_column("leg", sa.Column("chassis_at_end_id", sa.Integer(), nullable=True))
    op.add_column("leg", sa.Column("container_at_start_id", sa.Integer(), nullable=True))
    op.add_column("leg", sa.Column("container_at_end_id", sa.Integer(), nullable=True))
    op.add_column("leg", sa.Column("remarks", sa.String(length=500), nullable=True))
    op.create_foreign_key(
        "fk_leg_chassis_at_start_id", "leg", "chassis",
        ["chassis_at_start_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_leg_chassis_at_end_id", "leg", "chassis",
        ["chassis_at_end_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_leg_container_at_start_id", "leg", "container",
        ["container_at_start_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_leg_container_at_end_id", "leg", "container",
        ["container_at_end_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_leg_team_kind", "leg", ["team_id", "leg_kind"], unique=False)

    # ── 2) leg.status enum 확장 (DRY_RUN), move_type 확장 (BOBTAIL) ──
    op.execute(
        "ALTER TABLE leg MODIFY status ENUM('PENDING','IN_TRANSIT','COMPLETED','FAILED','DRY_RUN') NOT NULL DEFAULT 'PENDING'"
    )
    op.execute(
        "ALTER TABLE leg MODIFY move_type ENUM('LOADED','EMPTY','BOBTAIL') NOT NULL"
    )

    # ── 3) leg_stop 테이블 ─────────────────────────────────────
    op.create_table(
        "leg_stop",
        sa.Column("leg_id", sa.Integer(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column(
            "stop_kind",
            sa.Enum(
                "PICKUP_FULL", "DROP_FULL", "PICKUP_EMPTY", "DROP_EMPTY",
                "CHASSIS_GET", "CHASSIS_RETURN", "WAIT", "FUEL", "SCALE", "OTHER",
                name="stop_kind",
            ),
            nullable=False,
        ),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("container_id", sa.Integer(), nullable=True),
        sa.Column("chassis_id", sa.Integer(), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["leg_id"], ["leg.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["container_id"], ["container.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chassis_id"], ["chassis.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_leg_stop_team_id_id"),
        sa.UniqueConstraint("leg_id", "sequence_no", name="uq_leg_stop_leg_seq"),
    )
    op.create_index("ix_leg_stop_team_id", "leg_stop", ["team_id"], unique=False)
    op.create_index("ix_leg_stop_team_leg", "leg_stop", ["team_id", "leg_id"], unique=False)
    op.create_index("ix_leg_stop_team_kind", "leg_stop", ["team_id", "stop_kind"], unique=False)
    op.create_index("ix_leg_stop_team_active_id", "leg_stop", ["team_id", "is_active", "id"], unique=False)

    # ── 4) chassis_event 테이블 ───────────────────────────────
    op.create_table(
        "chassis_event",
        sa.Column("chassis_id", sa.Integer(), nullable=False),
        sa.Column("leg_id", sa.Integer(), nullable=True),
        sa.Column("leg_stop_id", sa.Integer(), nullable=True),
        sa.Column(
            "event_kind",
            sa.Enum(
                "PICKED_UP", "DROPPED_OFF", "FLIPPED",
                "RETURNED_TO_POOL", "RETURNED_TO_TERMINAL",
                name="chassis_event_kind",
            ),
            nullable=False,
        ),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["chassis_id"], ["chassis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leg_id"], ["leg.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["leg_stop_id"], ["leg_stop.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_chassis_event_team_id_id"),
    )
    op.create_index("ix_chassis_event_team_id", "chassis_event", ["team_id"], unique=False)
    op.create_index(
        "ix_chassis_event_team_chassis", "chassis_event",
        ["team_id", "chassis_id", "occurred_at"], unique=False,
    )
    op.create_index("ix_chassis_event_team_kind", "chassis_event", ["team_id", "event_kind"], unique=False)
    op.create_index("ix_chassis_event_team_active_id", "chassis_event", ["team_id", "is_active", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chassis_event_team_active_id", table_name="chassis_event")
    op.drop_index("ix_chassis_event_team_kind", table_name="chassis_event")
    op.drop_index("ix_chassis_event_team_chassis", table_name="chassis_event")
    op.drop_index("ix_chassis_event_team_id", table_name="chassis_event")
    op.drop_table("chassis_event")

    op.drop_index("ix_leg_stop_team_active_id", table_name="leg_stop")
    op.drop_index("ix_leg_stop_team_kind", table_name="leg_stop")
    op.drop_index("ix_leg_stop_team_leg", table_name="leg_stop")
    op.drop_index("ix_leg_stop_team_id", table_name="leg_stop")
    op.drop_table("leg_stop")

    op.execute(
        "ALTER TABLE leg MODIFY move_type ENUM('LOADED','EMPTY') NOT NULL"
    )
    op.execute(
        "ALTER TABLE leg MODIFY status ENUM('PENDING','IN_TRANSIT','COMPLETED','FAILED') NOT NULL DEFAULT 'PENDING'"
    )

    op.drop_index("ix_leg_team_kind", table_name="leg")
    op.drop_constraint("fk_leg_container_at_end_id", "leg", type_="foreignkey")
    op.drop_constraint("fk_leg_container_at_start_id", "leg", type_="foreignkey")
    op.drop_constraint("fk_leg_chassis_at_end_id", "leg", type_="foreignkey")
    op.drop_constraint("fk_leg_chassis_at_start_id", "leg", type_="foreignkey")
    op.drop_column("leg", "remarks")
    op.drop_column("leg", "container_at_end_id")
    op.drop_column("leg", "container_at_start_id")
    op.drop_column("leg", "chassis_at_end_id")
    op.drop_column("leg", "chassis_at_start_id")
    op.drop_column("leg", "leg_kind")
