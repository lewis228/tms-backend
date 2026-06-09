"""add rate_multiplier

Revision ID: e54b61c51195
Revises: 8fc7e605fcfc
Create Date: 2026-06-09 14:41:53.647874

NOTE: 신규 rate_multiplier 생성만 — 사전 드리프트 op 는 트리밍.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e54b61c51195'
down_revision: Union[str, None] = '8fc7e605fcfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rate_multiplier',
        sa.Column('rate_group_id', sa.Integer(), nullable=True),
        sa.Column('container_size', sa.Enum('SIZE_20', 'SIZE_40', 'SIZE_45', name='rate_multiplier_container_size'), nullable=False),
        sa.Column('factor', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rate_group_id'], ['rate_group.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_rate_multiplier_team_id_id'),
        sa.UniqueConstraint('team_id', 'rate_group_id', 'container_size', name='uq_rate_multiplier_scope_size'),
    )
    op.create_index('ix_rate_multiplier_team_active', 'rate_multiplier', ['team_id', 'is_active'], unique=False)
    op.create_index('ix_rate_multiplier_team_group', 'rate_multiplier', ['team_id', 'rate_group_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_rate_multiplier_team_group', table_name='rate_multiplier')
    op.drop_index('ix_rate_multiplier_team_active', table_name='rate_multiplier')
    op.drop_table('rate_multiplier')
