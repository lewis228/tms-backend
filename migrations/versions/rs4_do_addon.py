"""delivery_order_addon (D/O 단위 add-on → 고객 청구)

Revision ID: rs4_do_addon
Revises: rs3_addon_code
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs4_do_addon'
down_revision: Union[str, None] = 'rs3_addon_code'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'delivery_order_addon',
        sa.Column('delivery_order_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=48), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=2), server_default='1', nullable=False),
        sa.Column('unit_amount', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('extra', sa.JSON(), nullable=True),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['team_id', 'delivery_order_id'], ['delivery_order.team_id', 'delivery_order.id'],
            ondelete='CASCADE', name='fk_do_addon_do_team_id_id',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_do_addon_team_id_id'),
    )
    op.create_index(op.f('ix_delivery_order_addon_team_id'), 'delivery_order_addon', ['team_id'], unique=False)
    op.create_index('ix_do_addon_team_id_id', 'delivery_order_addon', ['team_id', 'id'], unique=False)
    op.create_index('ix_do_addon_team_do', 'delivery_order_addon', ['team_id', 'delivery_order_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_do_addon_team_do', table_name='delivery_order_addon')
    op.drop_index('ix_do_addon_team_id_id', table_name='delivery_order_addon')
    op.drop_index(op.f('ix_delivery_order_addon_team_id'), table_name='delivery_order_addon')
    op.drop_table('delivery_order_addon')
