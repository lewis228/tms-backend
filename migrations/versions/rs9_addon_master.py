"""addon master 통합: accessorial→addon rename, leg/do_addon→addon_id, charge_code drop

- charge_code 테이블 제거(고아 마스터).
- accessorial → addon 테이블 rename + is_billable_to_customer/is_payable_to_driver + 인덱스/제약 개명.
- payroll_charge.accessorial_id → addon_id, payroll_settlement.accessorial_total → addon_total.
- leg_addon.code(enum→varchar) + addon_id FK. delivery_order_addon.addon_id FK.
기존 데이터 폐기 가능 전제.

Revision ID: rs9_addon_master
Revises: rs8_leg_stop_addon
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs9_addon_master'
down_revision: Union[str, None] = 'rs8_leg_stop_addon'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEG_ADDON_ENUM = sa.Enum(
    "CHS", "HZM", "OOG", "RFR", "CXM", "LYO", "RSP", "FLT", "TNK", "NGT",
    "WKD", "EGT", "LFT", "PPS", "STP", "DET", "DMR", "YRD", name="leg_addon_code",
)

_ADDON_IDX_RENAME = [
    ("uq_accessorial_team_id_id", "uq_addon_team_id_id"),
    ("uq_accessorial_code_driver", "uq_addon_code_driver"),
    ("ix_accessorial_team_active_id", "ix_addon_team_active_id"),
    ("ix_accessorial_team_category", "ix_addon_team_category"),
    ("ix_accessorial_team_code", "ix_addon_team_code"),
    ("ix_accessorial_team_driver", "ix_addon_team_driver"),
    ("ix_accessorial_team_id", "ix_addon_team_id"),
    ("ix_accessorial_team_updated_at", "ix_addon_team_updated_at"),
]


def upgrade() -> None:
    # 1) charge_code 제거
    op.drop_table("charge_code")

    # 2) accessorial → addon (FK 는 rename_table 이 자동 추종)
    op.rename_table("accessorial", "addon")
    op.add_column("addon", sa.Column("is_billable_to_customer", sa.Boolean(), server_default="1", nullable=False))
    op.add_column("addon", sa.Column("is_payable_to_driver", sa.Boolean(), server_default="1", nullable=False))
    for old, new in _ADDON_IDX_RENAME:
        op.execute(f"ALTER TABLE addon RENAME INDEX `{old}` TO `{new}`")

    # 3) payroll_charge.accessorial_id → addon_id (FK 컬럼 rename — MySQL 이 FK 추종)
    op.alter_column("payroll_charge", "accessorial_id", new_column_name="addon_id", existing_type=sa.Integer())
    # FK 암묵 인덱스도 컬럼명과 맞춰 rename (alembic 이 FK 인덱스로 인식하도록)
    op.execute("ALTER TABLE payroll_charge RENAME INDEX `accessorial_id` TO `addon_id`")
    # 4) payroll_settlement.accessorial_total → addon_total
    op.alter_column("payroll_settlement", "accessorial_total", new_column_name="addon_total",
                    existing_type=sa.Numeric(14, 2), existing_nullable=False, existing_server_default="0")

    # 5) leg_addon: code enum→varchar + addon_id FK
    op.alter_column("leg_addon", "code", existing_type=_LEG_ADDON_ENUM,
                    type_=sa.String(length=48), existing_nullable=False)
    op.add_column("leg_addon", sa.Column("addon_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_leg_addon_addon", "leg_addon", "addon", ["addon_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_leg_addon_team_addon", "leg_addon", ["team_id", "addon_id"])

    # 6) delivery_order_addon: addon_id FK
    op.add_column("delivery_order_addon", sa.Column("addon_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_do_addon_addon", "delivery_order_addon", "addon", ["addon_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_do_addon_addon", "delivery_order_addon", type_="foreignkey")
    op.drop_column("delivery_order_addon", "addon_id")

    op.drop_index("ix_leg_addon_team_addon", table_name="leg_addon")
    op.drop_constraint("fk_leg_addon_addon", "leg_addon", type_="foreignkey")
    op.drop_column("leg_addon", "addon_id")
    op.alter_column("leg_addon", "code", existing_type=sa.String(length=48),
                    type_=_LEG_ADDON_ENUM, existing_nullable=False)

    op.alter_column("payroll_settlement", "addon_total", new_column_name="accessorial_total",
                    existing_type=sa.Numeric(14, 2), existing_nullable=False, existing_server_default="0")
    op.execute("ALTER TABLE payroll_charge RENAME INDEX `addon_id` TO `accessorial_id`")
    op.alter_column("payroll_charge", "addon_id", new_column_name="accessorial_id", existing_type=sa.Integer())

    for old, new in _ADDON_IDX_RENAME:
        op.execute(f"ALTER TABLE addon RENAME INDEX `{new}` TO `{old}`")
    op.drop_column("addon", "is_payable_to_driver")
    op.drop_column("addon", "is_billable_to_customer")
    op.rename_table("addon", "accessorial")

    op.create_table(
        "charge_code",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_charge_code_team_id_id"),
    )
