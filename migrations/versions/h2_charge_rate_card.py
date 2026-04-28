"""H-2 charge_code + rate_card + leg_charge

Revision ID: h2charge0002
Revises: h1container0001
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h2charge0002"
down_revision: Union[str, None] = "h1container0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) charge_code ─────────────────────────────────────────
    op.create_table(
        "charge_code",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "BASE", "ACCESSORIAL", "PENALTY", "FUEL", "TAX", "DISCOUNT",
                name="charge_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "default_unit",
            sa.Enum(
                "FLAT", "HOUR", "MINUTE", "DAY", "MILE", "PERCENT",
                name="charge_unit",
            ),
            server_default="FLAT", nullable=False,
        ),
        sa.Column("default_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("is_billable_to_customer", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("is_payable_to_driver", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("gl_account", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_charge_code_team_id_id"),
        sa.UniqueConstraint("team_id", "code", name="uq_charge_code_team_code"),
    )
    op.create_index("ix_charge_code_team_id", "charge_code", ["team_id"], unique=False)
    op.create_index("ix_charge_code_team_kind", "charge_code", ["team_id", "kind"], unique=False)
    op.create_index("ix_charge_code_team_active_id", "charge_code", ["team_id", "is_active", "id"], unique=False)

    # ── 2) rate_card ───────────────────────────────────────────
    op.create_table(
        "rate_card",
        sa.Column("charge_code_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("scope_customer_id", sa.Integer(), nullable=True),
        sa.Column("scope_terminal_id", sa.Integer(), nullable=True),
        sa.Column(
            "scope_size",
            sa.Enum(
                "SIZE_20GP", "SIZE_40GP", "SIZE_40HC", "SIZE_40OT",
                "SIZE_45HC", "SIZE_20RF", "SIZE_40RF",
                name="container_size",
            ),
            nullable=True,
        ),
        sa.Column("scope_zone", sa.String(length=64), nullable=True),
        sa.Column("scope_from_location_id", sa.Integer(), nullable=True),
        sa.Column("scope_to_location_id", sa.Integer(), nullable=True),
        sa.Column(
            "unit",
            sa.Enum(
                "FLAT", "HOUR", "MINUTE", "DAY", "MILE", "PERCENT",
                name="charge_unit",
            ),
            server_default="FLAT", nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("percent", sa.Numeric(7, 4), nullable=True),
        sa.Column("per_unit", sa.Numeric(14, 4), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["charge_code_id"], ["charge_code.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_customer_id"], ["customer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_terminal_id"], ["terminal.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_from_location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scope_to_location_id"], ["location.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_rate_card_team_id_id"),
    )
    op.create_index("ix_rate_card_team_id", "rate_card", ["team_id"], unique=False)
    op.create_index("ix_rate_card_team_charge_code", "rate_card", ["team_id", "charge_code_id"], unique=False)
    op.create_index("ix_rate_card_team_customer", "rate_card", ["team_id", "scope_customer_id"], unique=False)
    op.create_index("ix_rate_card_team_terminal", "rate_card", ["team_id", "scope_terminal_id"], unique=False)
    op.create_index("ix_rate_card_team_priority", "rate_card", ["team_id", "priority"], unique=False)
    op.create_index("ix_rate_card_team_effective", "rate_card", ["team_id", "effective_from"], unique=False)
    op.create_index("ix_rate_card_team_active_id", "rate_card", ["team_id", "is_active", "id"], unique=False)

    # ── 3) leg_charge ──────────────────────────────────────────
    op.create_table(
        "leg_charge",
        sa.Column("leg_id", sa.Integer(), nullable=False),
        sa.Column("charge_code_id", sa.Integer(), nullable=False),
        sa.Column("rate_card_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "unit",
            sa.Enum(
                "FLAT", "HOUR", "MINUTE", "DAY", "MILE", "PERCENT",
                name="charge_unit",
            ),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.Enum("AUTO", "MANUAL", "EVENT", name="charge_source"),
            server_default="MANUAL", nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("settlement_id", sa.Integer(), nullable=True),
        sa.Column("is_settled", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("payee_kind", sa.String(length=32), nullable=True),
        sa.Column("payee_driver_id", sa.Integer(), nullable=True),
        sa.Column("payer_kind", sa.String(length=32), nullable=True),
        sa.Column("payer_partner_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["charge_code_id"], ["charge_code.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rate_card_id"], ["rate_card.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["settlement_id"], ["settlement.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payee_driver_id"], ["driver.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payer_partner_id"], ["customer.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_leg_charge_team_id_id"),
    )
    op.create_index("ix_leg_charge_team_id", "leg_charge", ["team_id"], unique=False)
    op.create_index("ix_leg_charge_team_leg", "leg_charge", ["team_id", "leg_id"], unique=False)
    op.create_index("ix_leg_charge_team_charge_code", "leg_charge", ["team_id", "charge_code_id"], unique=False)
    op.create_index("ix_leg_charge_team_settlement", "leg_charge", ["team_id", "settlement_id"], unique=False)
    op.create_index("ix_leg_charge_team_source", "leg_charge", ["team_id", "source"], unique=False)
    op.create_index("ix_leg_charge_team_active_id", "leg_charge", ["team_id", "is_active", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leg_charge_team_active_id", table_name="leg_charge")
    op.drop_index("ix_leg_charge_team_source", table_name="leg_charge")
    op.drop_index("ix_leg_charge_team_settlement", table_name="leg_charge")
    op.drop_index("ix_leg_charge_team_charge_code", table_name="leg_charge")
    op.drop_index("ix_leg_charge_team_leg", table_name="leg_charge")
    op.drop_index("ix_leg_charge_team_id", table_name="leg_charge")
    op.drop_table("leg_charge")

    op.drop_index("ix_rate_card_team_active_id", table_name="rate_card")
    op.drop_index("ix_rate_card_team_effective", table_name="rate_card")
    op.drop_index("ix_rate_card_team_priority", table_name="rate_card")
    op.drop_index("ix_rate_card_team_terminal", table_name="rate_card")
    op.drop_index("ix_rate_card_team_customer", table_name="rate_card")
    op.drop_index("ix_rate_card_team_charge_code", table_name="rate_card")
    op.drop_index("ix_rate_card_team_id", table_name="rate_card")
    op.drop_table("rate_card")

    op.drop_index("ix_charge_code_team_active_id", table_name="charge_code")
    op.drop_index("ix_charge_code_team_kind", table_name="charge_code")
    op.drop_index("ix_charge_code_team_id", table_name="charge_code")
    op.drop_table("charge_code")
