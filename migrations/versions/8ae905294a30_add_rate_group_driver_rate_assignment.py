"""add rate_group, driver_rate_assignment

Revision ID: 8ae905294a30
Revises: 374f4dc66d33
Create Date: 2026-06-09 14:20:56.632278

NOTE: autogenerate 가 기존 모델↔DB 사전 드리프트(container_size enum, team_id 인덱스 등)도
함께 잡았으나, 이 마이그레이션은 신규 rate_group / driver_rate_assignment 생성만 담당하도록
트리밍했다. (드리프트는 baseline 재정비 단계에서 일괄 정리)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8ae905294a30'
down_revision: Union[str, None] = '374f4dc66d33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create rate_group + driver_rate_assignment only."""
    op.create_table(
        'rate_group',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('method', sa.Enum('ZONE', 'CITY', 'MILE', 'HOURLY', name='rate_method'), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('is_template', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_rate_group_team_id_id'),
    )
    op.create_index('ix_rate_group_team_active_id', 'rate_group', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_rate_group_team_id'), 'rate_group', ['team_id'], unique=False)
    op.create_index('ix_rate_group_team_method', 'rate_group', ['team_id', 'method'], unique=False)
    op.create_index('ix_rate_group_team_updated_at', 'rate_group', ['team_id', 'updated_at'], unique=False)

    op.create_table(
        'driver_rate_assignment',
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('rate_group_id', sa.Integer(), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['driver_id'], ['driver.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rate_group_id'], ['rate_group.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_driver_rate_assign_team_id_id'),
    )
    op.create_index('ix_driver_rate_assign_lookup', 'driver_rate_assignment', ['team_id', 'driver_id', 'effective_from'], unique=False)
    op.create_index('ix_driver_rate_assign_team_active_id', 'driver_rate_assignment', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_driver_rate_assign_team_group', 'driver_rate_assignment', ['team_id', 'rate_group_id'], unique=False)
    op.create_index('ix_driver_rate_assign_team_updated_at', 'driver_rate_assignment', ['team_id', 'updated_at'], unique=False)
    op.create_index(op.f('ix_driver_rate_assignment_team_id'), 'driver_rate_assignment', ['team_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema — drop the two tables only."""
    op.drop_index(op.f('ix_driver_rate_assignment_team_id'), table_name='driver_rate_assignment')
    op.drop_index('ix_driver_rate_assign_team_updated_at', table_name='driver_rate_assignment')
    op.drop_index('ix_driver_rate_assign_team_group', table_name='driver_rate_assignment')
    op.drop_index('ix_driver_rate_assign_team_active_id', table_name='driver_rate_assignment')
    op.drop_index('ix_driver_rate_assign_lookup', table_name='driver_rate_assignment')
    op.drop_table('driver_rate_assignment')
    op.drop_index('ix_rate_group_team_updated_at', table_name='rate_group')
    op.drop_index('ix_rate_group_team_method', table_name='rate_group')
    op.drop_index(op.f('ix_rate_group_team_id'), table_name='rate_group')
    op.drop_index('ix_rate_group_team_active_id', table_name='rate_group')
    op.drop_table('rate_group')
