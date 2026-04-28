"""H-8 street_turn 승인 워크플로우 + container_id

Revision ID: h8street00008
Revises: h7payee00007
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8street00008"
down_revision: Union[str, None] = "h7payee00007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) container_number nullable 로 완화 (container_id FK 로 대체 가능) ──
    op.alter_column(
        "street_turn", "container_number",
        existing_type=sa.String(length=11),
        nullable=True,
    )

    # ── 2) container_id 추가 ──
    op.add_column("street_turn", sa.Column("container_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_street_turn_container_id", "street_turn", "container",
        ["container_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_street_turn_team_container_id",
        "street_turn", ["team_id", "container_id"], unique=False,
    )

    # ── 3) 승인 워크플로우 컬럼 ──
    op.add_column(
        "street_turn",
        sa.Column(
            "status",
            sa.Enum("REQUESTED", "APPROVED", "REJECTED", "CANCELLED", name="street_turn_status"),
            server_default="REQUESTED", nullable=False,
        ),
    )
    op.add_column("street_turn", sa.Column("carrier_approval_no", sa.String(length=64), nullable=True))
    op.add_column("street_turn", sa.Column("requested_by", sa.Integer(), nullable=True))
    op.add_column("street_turn", sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("street_turn", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.add_column("street_turn", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("street_turn", sa.Column("rejected_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_street_turn_requested_by", "street_turn", "user",
        ["requested_by"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_street_turn_approved_by", "street_turn", "user",
        ["approved_by"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_street_turn_team_status", "street_turn", ["team_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_street_turn_team_status", table_name="street_turn")
    op.drop_constraint("fk_street_turn_approved_by", "street_turn", type_="foreignkey")
    op.drop_constraint("fk_street_turn_requested_by", "street_turn", type_="foreignkey")
    op.drop_column("street_turn", "rejected_reason")
    op.drop_column("street_turn", "approved_at")
    op.drop_column("street_turn", "approved_by")
    op.drop_column("street_turn", "requested_at")
    op.drop_column("street_turn", "requested_by")
    op.drop_column("street_turn", "carrier_approval_no")
    op.drop_column("street_turn", "status")

    op.drop_index("ix_street_turn_team_container_id", table_name="street_turn")
    op.drop_constraint("fk_street_turn_container_id", "street_turn", type_="foreignkey")
    op.drop_column("street_turn", "container_id")

    op.alter_column(
        "street_turn", "container_number",
        existing_type=sa.String(length=11),
        nullable=False,
    )
