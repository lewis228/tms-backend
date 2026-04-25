"""add tags, ocean_shipment_tags and shipment meta fields (customer, ref_numbers)

Revision ID: d4e5f6g7h8i9
Revises: 718c062ccc68
Create Date: 2026-04-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6g7h8i9"
down_revision: Union[str, None] = "718c062ccc68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tags ────────────────────────────────────────────
    op.create_table(
        "tags",
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "name", name="uq_tags_team_name"),
    )
    op.create_index("ix_tags_team_id", "tags", ["team_id"], unique=False)

    # ── ocean_shipments metadata columns ────────────────
    op.add_column(
        "ocean_shipments",
        sa.Column("customer", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "ocean_shipments",
        sa.Column("ref_numbers", sa.JSON(), nullable=True),
    )

    # ── ocean_shipment_tags (join) ──────────────────────
    op.create_table(
        "ocean_shipment_tags",
        sa.Column("shipment_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["shipment_id"], ["ocean_shipments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "shipment_id", "tag_id", name="uq_ocean_shipment_tags"
        ),
    )
    op.create_index(
        "ix_ocean_shipment_tags_shipment_id",
        "ocean_shipment_tags",
        ["shipment_id"],
        unique=False,
    )
    op.create_index(
        "ix_ocean_shipment_tags_tag_id",
        "ocean_shipment_tags",
        ["tag_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ocean_shipment_tags_tag_id", table_name="ocean_shipment_tags")
    op.drop_index(
        "ix_ocean_shipment_tags_shipment_id", table_name="ocean_shipment_tags"
    )
    op.drop_table("ocean_shipment_tags")

    op.drop_column("ocean_shipments", "ref_numbers")
    op.drop_column("ocean_shipments", "customer")

    op.drop_index("ix_tags_team_id", table_name="tags")
    op.drop_table("tags")
