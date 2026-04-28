"""H-7 leg_charge payee/payer 확장 (PartyKind enum + payee_partner_id + payee_pool_id)

Revision ID: h7payee00007
Revises: h6stop00006
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h7payee00007"
down_revision: Union[str, None] = "h6stop00006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) leg_charge.payee_kind/payer_kind: String(32) → Enum(PartyKind) ──
    party_kind_values = "'CUSTOMER','CARRIER','DRIVER','COMPANY','POOL'"
    op.execute(
        f"ALTER TABLE leg_charge MODIFY payee_kind ENUM({party_kind_values}) NULL"
    )
    op.execute(
        f"ALTER TABLE leg_charge MODIFY payer_kind ENUM({party_kind_values}) NULL"
    )

    # ── 2) payee_partner_id, payee_pool_id 컬럼 추가 ──
    op.add_column("leg_charge", sa.Column("payee_partner_id", sa.Integer(), nullable=True))
    op.add_column("leg_charge", sa.Column("payee_pool_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_leg_charge_payee_partner_id", "leg_charge", "customer",
        ["payee_partner_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_leg_charge_payee_pool_id", "leg_charge", "equipment_pool",
        ["payee_pool_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_leg_charge_team_payee_partner",
        "leg_charge", ["team_id", "payee_partner_id"], unique=False,
    )
    op.create_index(
        "ix_leg_charge_team_payee_driver",
        "leg_charge", ["team_id", "payee_driver_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_leg_charge_team_payee_driver", table_name="leg_charge")
    op.drop_index("ix_leg_charge_team_payee_partner", table_name="leg_charge")
    op.drop_constraint("fk_leg_charge_payee_pool_id", "leg_charge", type_="foreignkey")
    op.drop_constraint("fk_leg_charge_payee_partner_id", "leg_charge", type_="foreignkey")
    op.drop_column("leg_charge", "payee_pool_id")
    op.drop_column("leg_charge", "payee_partner_id")
    op.execute("ALTER TABLE leg_charge MODIFY payer_kind VARCHAR(32) NULL")
    op.execute("ALTER TABLE leg_charge MODIFY payee_kind VARCHAR(32) NULL")
