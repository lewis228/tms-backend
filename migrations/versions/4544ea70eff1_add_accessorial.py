"""add accessorial

Revision ID: 4544ea70eff1
Revises: 12c8eebd65d3
Create Date: 2026-06-09 15:05:00.000000

NOTE: 신규 accessorial 생성만 — 사전 드리프트 트리밍.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '4544ea70eff1'
down_revision: Union[str, None] = '12c8eebd65d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'accessorial',
        sa.Column('code', sa.String(length=48), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('category', sa.Enum('WAITING', 'EXTRA_STOP', 'DRY_RUN', 'PENALTY', 'SURCHARGE', 'FUEL', 'CHASSIS_SPLIT', 'PREPULL', 'LIFT', 'NIGHT_GATE', 'PIER_PASS', 'HAZMAT', 'REEFER', 'OVERWEIGHT', 'STORAGE', 'ADJUSTMENT', 'OTHER', name='accessorial_category'), nullable=False),
        sa.Column('unit', sa.Enum('FLAT', 'HOUR', 'MINUTE', 'DAY', 'MILE', 'PERCENT', name='accessorial_unit'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('percent', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('free_minutes', sa.Integer(), nullable=True),
        sa.Column('free_days', sa.Integer(), nullable=True),
        sa.Column('auto_apply', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('is_system', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['driver_id'], ['driver.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'code', 'driver_id', name='uq_accessorial_code_driver'),
        sa.UniqueConstraint('team_id', 'id', name='uq_accessorial_team_id_id'),
    )
    op.create_index('ix_accessorial_team_active_id', 'accessorial', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_accessorial_team_category', 'accessorial', ['team_id', 'category'], unique=False)
    op.create_index('ix_accessorial_team_code', 'accessorial', ['team_id', 'code'], unique=False)
    op.create_index('ix_accessorial_team_driver', 'accessorial', ['team_id', 'driver_id'], unique=False)
    op.create_index(op.f('ix_accessorial_team_id'), 'accessorial', ['team_id'], unique=False)
    op.create_index('ix_accessorial_team_updated_at', 'accessorial', ['team_id', 'updated_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_accessorial_team_updated_at', table_name='accessorial')
    op.drop_index(op.f('ix_accessorial_team_id'), table_name='accessorial')
    op.drop_index('ix_accessorial_team_driver', table_name='accessorial')
    op.drop_index('ix_accessorial_team_code', table_name='accessorial')
    op.drop_index('ix_accessorial_team_category', table_name='accessorial')
    op.drop_index('ix_accessorial_team_active_id', table_name='accessorial')
    op.drop_table('accessorial')
