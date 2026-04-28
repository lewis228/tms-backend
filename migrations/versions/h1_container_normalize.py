"""H-1 container normalize: D/O 1:N container + container_event + leg.container_id

Revision ID: h1container0001
Revises: 2422688cd53e
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "h1container0001"
down_revision: Union[str, None] = "2422688cd53e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# delivery_order 에서 옮겨갈 / 제거할 컬럼 (백업용)
_DO_DROP_COLUMNS = [
    "container_number",
    "container_size",
    "container_type",
    "chassis_number",
    "pickup_appointment",
    "delivery_appointment",
    "return_appointment",
    "demurrage_lfd",
    "detention_lfd",
    "empty_date",
    "loaded_date",
    "pier_pass_paid",
    "customs_cleared",
]


def upgrade() -> None:
    # ── 1) container 테이블 ─────────────────────────────────────
    op.create_table(
        "container",
        sa.Column("delivery_order_id", sa.Integer(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("container_number", sa.String(length=11), nullable=True),
        sa.Column("seal_no", sa.String(length=64), nullable=True),
        sa.Column(
            "size",
            sa.Enum(
                "SIZE_20GP", "SIZE_40GP", "SIZE_40HC", "SIZE_40OT",
                "SIZE_45HC", "SIZE_20RF", "SIZE_40RF",
                name="container_size",
            ),
            nullable=True,
        ),
        sa.Column("type", sa.String(length=32), nullable=True),
        sa.Column("weight_kg", sa.Numeric(12, 2), nullable=True),
        sa.Column("chassis_number", sa.String(length=32), nullable=True),
        sa.Column("pickup_appointment", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_appointment", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_appointment", sa.DateTime(timezone=True), nullable=True),
        sa.Column("demurrage_lfd", sa.Date(), nullable=True),
        sa.Column("detention_lfd", sa.Date(), nullable=True),
        sa.Column("empty_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("loaded_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_location_id", sa.Integer(), nullable=True),
        sa.Column("return_location_id", sa.Integer(), nullable=True),
        sa.Column(
            "service_type",
            sa.Enum("LIVE", "DROP", name="service_type"),
            nullable=True,
        ),
        sa.Column("pier_pass_paid", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("customs_cleared", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PLANNING", "DISPATCHED", "YARD_STAGED",
                "FINAL_DELIVERY", "EMPTY_STAGED", "COMPLETED",
                name="delivery_status",
            ),
            server_default="PLANNING",
            nullable=False,
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
        sa.ForeignKeyConstraint(["delivery_order_id"], ["delivery_order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delivery_location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["return_location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_container_team_id_id"),
        sa.UniqueConstraint("delivery_order_id", "sequence_no", name="uq_container_do_seq"),
    )
    op.create_index("ix_container_team_id", "container", ["team_id"], unique=False)
    op.create_index("ix_container_team_do", "container", ["team_id", "delivery_order_id"], unique=False)
    op.create_index("ix_container_team_number", "container", ["team_id", "container_number"], unique=False)
    op.create_index("ix_container_team_status", "container", ["team_id", "status"], unique=False)
    op.create_index("ix_container_team_demurrage", "container", ["team_id", "demurrage_lfd"], unique=False)
    op.create_index("ix_container_team_detention", "container", ["team_id", "detention_lfd"], unique=False)
    op.create_index("ix_container_team_active_id", "container", ["team_id", "is_active", "id"], unique=False)
    op.create_index("ix_container_team_updated_at", "container", ["team_id", "updated_at"], unique=False)

    # ── 2) container_event 테이블 ───────────────────────────────
    op.create_table(
        "container_event",
        sa.Column("container_id", sa.Integer(), nullable=False),
        sa.Column("leg_id", sa.Integer(), nullable=True),
        sa.Column(
            "event_kind",
            sa.Enum(
                "GATE_OUT", "DELIVERED", "EMPTIED", "STREET_TURNED",
                "REUSED", "GATE_IN", "RETURNED",
                name="container_event_kind",
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
        sa.ForeignKeyConstraint(["container_id"], ["container.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leg_id"], ["leg.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_container_event_team_id_id"),
    )
    op.create_index("ix_container_event_team_id", "container_event", ["team_id"], unique=False)
    op.create_index("ix_container_event_team_container", "container_event", ["team_id", "container_id", "occurred_at"], unique=False)
    op.create_index("ix_container_event_team_kind", "container_event", ["team_id", "event_kind"], unique=False)
    op.create_index("ix_container_event_team_active_id", "container_event", ["team_id", "is_active", "id"], unique=False)

    # ── 3) leg.container_id 추가 ────────────────────────────────
    op.add_column("leg", sa.Column("container_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_leg_container_id",
        "leg",
        "container",
        ["container_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_leg_team_container", "leg", ["team_id", "container_id"], unique=False)

    # ── 4) delivery_order 슬림화 ────────────────────────────────
    # delivery_location_id / return_location_id 는 FK 명시되어 있으므로 FK 먼저 drop
    with op.batch_alter_table("delivery_order") as batch:
        for fk_name in (
            "delivery_order_ibfk_2",  # delivery_location_id
            "delivery_order_ibfk_4",  # return_location_id
        ):
            try:
                batch.drop_constraint(fk_name, type_="foreignkey")
            except Exception:
                pass

    # 1차 시도: 이름이 다를 수 있으므로 inspector 로 컬럼 + FK 정리
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fks = inspector.get_foreign_keys("delivery_order")
    fk_names_to_drop = []
    for fk in fks:
        cols = fk.get("constrained_columns") or []
        if "delivery_location_id" in cols or "return_location_id" in cols:
            name = fk.get("name")
            if name:
                fk_names_to_drop.append(name)
    for name in fk_names_to_drop:
        try:
            op.drop_constraint(name, "delivery_order", type_="foreignkey")
        except Exception:
            pass

    # 컬럼 drop (delivery_location_id / return_location_id + 일정/게이트/컨테이너 컬럼)
    for col in ("delivery_location_id", "return_location_id", *_DO_DROP_COLUMNS):
        try:
            op.drop_column("delivery_order", col)
        except Exception:
            pass


def downgrade() -> None:
    # ── 4) delivery_order 컬럼 복원 ─────────────────────────────
    op.add_column("delivery_order", sa.Column("customs_cleared", sa.Boolean(), server_default="0", nullable=False))
    op.add_column("delivery_order", sa.Column("pier_pass_paid", sa.Boolean(), server_default="0", nullable=False))
    op.add_column("delivery_order", sa.Column("loaded_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_order", sa.Column("empty_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_order", sa.Column("detention_lfd", sa.Date(), nullable=True))
    op.add_column("delivery_order", sa.Column("demurrage_lfd", sa.Date(), nullable=True))
    op.add_column("delivery_order", sa.Column("return_appointment", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_order", sa.Column("delivery_appointment", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_order", sa.Column("pickup_appointment", sa.DateTime(timezone=True), nullable=True))
    op.add_column("delivery_order", sa.Column("chassis_number", sa.String(length=32), nullable=True))
    op.add_column("delivery_order", sa.Column("container_type", sa.String(length=32), nullable=True))
    op.add_column(
        "delivery_order",
        sa.Column(
            "container_size",
            sa.Enum(
                "SIZE_20GP", "SIZE_40GP", "SIZE_40HC", "SIZE_40OT",
                "SIZE_45HC", "SIZE_20RF", "SIZE_40RF",
                name="container_size",
            ),
            nullable=True,
        ),
    )
    op.add_column("delivery_order", sa.Column("container_number", sa.String(length=11), nullable=True))
    op.add_column("delivery_order", sa.Column("return_location_id", sa.Integer(), nullable=True))
    op.add_column("delivery_order", sa.Column("delivery_location_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_do_delivery_loc",
        "delivery_order",
        "location",
        ["delivery_location_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_do_return_loc",
        "delivery_order",
        "location",
        ["return_location_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── 3) leg.container_id ──
    op.drop_index("ix_leg_team_container", table_name="leg")
    op.drop_constraint("fk_leg_container_id", "leg", type_="foreignkey")
    op.drop_column("leg", "container_id")

    # ── 2) container_event ──
    op.drop_index("ix_container_event_team_active_id", table_name="container_event")
    op.drop_index("ix_container_event_team_kind", table_name="container_event")
    op.drop_index("ix_container_event_team_container", table_name="container_event")
    op.drop_index("ix_container_event_team_id", table_name="container_event")
    op.drop_table("container_event")

    # ── 1) container ──
    op.drop_index("ix_container_team_updated_at", table_name="container")
    op.drop_index("ix_container_team_active_id", table_name="container")
    op.drop_index("ix_container_team_detention", table_name="container")
    op.drop_index("ix_container_team_demurrage", table_name="container")
    op.drop_index("ix_container_team_status", table_name="container")
    op.drop_index("ix_container_team_number", table_name="container")
    op.drop_index("ix_container_team_do", table_name="container")
    op.drop_index("ix_container_team_id", table_name="container")
    op.drop_table("container")
