"""rate_zone_member: 미사용 city/state 폐기, zip_code NOT NULL

존(zone) = 순수 zip 묶음. resolver 는 zip_code 만 매칭하므로 city/state 는 죽은 컬럼 → 제거.
(도시별 요율은 CITY 방식의 rate_entry.col_city 가 별도 담당 — zone_member 와 무관.)
기존 데이터 폐기 가능 전제(시드 재생성).

Revision ID: rs11_drop_zone_member_city
Revises: rs10_addon_flags
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs11_drop_zone_member_city'
down_revision: Union[str, None] = 'rs10_addon_flags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # city/state 로만 정의된 멤버는 zip 정산에서 안 잡히는 죽은 데이터 → 정리(폐기 가능 전제)
    op.execute("DELETE FROM rate_zone_member WHERE zip_code IS NULL")
    op.drop_index("ix_rate_zone_member_team_city", table_name="rate_zone_member")
    op.drop_column("rate_zone_member", "city")
    op.drop_column("rate_zone_member", "state")
    op.alter_column("rate_zone_member", "zip_code",
                    existing_type=sa.String(length=16), nullable=False)


def downgrade() -> None:
    op.alter_column("rate_zone_member", "zip_code",
                    existing_type=sa.String(length=16), nullable=True)
    op.add_column("rate_zone_member", sa.Column("state", sa.String(length=8), nullable=True))
    op.add_column("rate_zone_member", sa.Column("city", sa.String(length=120), nullable=True))
    op.create_index("ix_rate_zone_member_team_city", "rate_zone_member", ["team_id", "city", "state"])
