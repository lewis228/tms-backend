"""zip_code 전역 마스터 생성 + location/customer/terminal 에 zip_id FK

- zip_code: 미국 우편번호 전역 reference(zip/city/state/county/lat/lng).
- location/customer/terminal.zip_id → zip_code.id (ondelete SET NULL): 정산 dest 자동채움용.
순서: 테이블 먼저 create → FK 컬럼 add.

Revision ID: rs12_zip_master
Revises: rs11_drop_zone_member_city
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs12_zip_master'
down_revision: Union[str, None] = 'rs11_drop_zone_member_city'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MASTERS = ("location", "customer", "terminal")


def upgrade() -> None:
    op.create_table(
        "zip_code",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("zip", sa.String(length=16), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.Column("county", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zip", name="uq_zip_code_zip"),
    )
    op.create_index("ix_zip_code_zip", "zip_code", ["zip"])
    op.create_index("ix_zip_code_state_city", "zip_code", ["state", "city"])
    op.create_index("ix_zip_code_city", "zip_code", ["city"])

    for t in _MASTERS:
        op.add_column(t, sa.Column("zip_id", sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{t}_zip_id", t, "zip_code", ["zip_id"], ["id"], ondelete="SET NULL")
        op.create_index(f"ix_{t}_team_zip", t, ["team_id", "zip_id"])


def downgrade() -> None:
    for t in _MASTERS:
        op.drop_index(f"ix_{t}_team_zip", table_name=t)
        op.drop_constraint(f"fk_{t}_zip_id", t, type_="foreignkey")
        op.drop_column(t, "zip_id")
    op.drop_index("ix_zip_code_city", table_name="zip_code")
    op.drop_index("ix_zip_code_state_city", table_name="zip_code")
    op.drop_index("ix_zip_code_zip", table_name="zip_code")
    op.drop_table("zip_code")
