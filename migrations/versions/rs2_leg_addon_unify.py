"""leg_addon 통합 add-on (중복 허용 + amount/quantity/unit_amount 1급)

Revision ID: rs2_addon_unify
Revises: rs1_service_type
Create Date: 2026-06-10

컨플루언스 재정의: Layer 1/2/3 폐기. leg 추가요금은 모두 Add-on(같은 code 중복 가능,
amount 가 확정 금액 — 자동 채움 + 사용자 수정). uq(team,leg,code) 제거.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs2_addon_unify'
down_revision: Union[str, None] = 'rs1_service_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leg_addon', sa.Column('quantity', sa.Numeric(12, 2), server_default='1', nullable=False))
    op.add_column('leg_addon', sa.Column('unit_amount', sa.Numeric(14, 2), nullable=True))
    op.add_column('leg_addon', sa.Column('amount', sa.Numeric(14, 2), server_default='0', nullable=False))
    op.drop_constraint('uq_leg_addon_leg_code', 'leg_addon', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('uq_leg_addon_leg_code', 'leg_addon', ['team_id', 'leg_id', 'code'])
    op.drop_column('leg_addon', 'amount')
    op.drop_column('leg_addon', 'unit_amount')
    op.drop_column('leg_addon', 'quantity')
