"""add rate_sheet, rate_entry, rate_entry_history

Revision ID: 8fc7e605fcfc
Revises: 2eea89deba4c
Create Date: 2026-06-09 14:45:00.000000

NOTE: autogenerate 가 기존 모델↔DB 사전 드리프트도 함께 잡았으나, 이 마이그레이션은
신규 rate_sheet / rate_entry / rate_entry_history 생성만 담당하도록 트리밍했다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8fc7e605fcfc'
down_revision: Union[str, None] = '2eea89deba4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create rate_sheet + rate_entry + rate_entry_history only."""
    op.create_table(
        'rate_sheet',
        sa.Column('rate_group_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.Enum('POINT_ZONE', 'POINT_CITY', 'POINT_POINT', 'MILE', 'HOURLY', name='rate_sheet_kind'), nullable=False),
        sa.Column('move_type', sa.Enum('LOAD', 'EMPTY', 'NONE', name='rate_move_type'), nullable=True),
        sa.Column('row_point_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['rate_group_id'], ['rate_group.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['row_point_id'], ['rate_point.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_rate_sheet_team_id_id'),
        sa.UniqueConstraint('team_id', 'rate_group_id', 'kind', 'move_type', 'row_point_id', name='uq_rate_sheet_slot'),
    )
    op.create_index('ix_rate_sheet_team_active_id', 'rate_sheet', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_rate_sheet_team_group', 'rate_sheet', ['team_id', 'rate_group_id'], unique=False)
    op.create_index(op.f('ix_rate_sheet_team_id'), 'rate_sheet', ['team_id'], unique=False)
    op.create_index('ix_rate_sheet_team_kind', 'rate_sheet', ['team_id', 'kind'], unique=False)
    op.create_index('ix_rate_sheet_team_updated_at', 'rate_sheet', ['team_id', 'updated_at'], unique=False)

    op.create_table(
        'rate_entry',
        sa.Column('rate_sheet_id', sa.Integer(), nullable=False),
        sa.Column('col_zone_id', sa.Integer(), nullable=True),
        sa.Column('col_point_id', sa.Integer(), nullable=True),
        sa.Column('col_city', sa.String(length=120), nullable=True),
        sa.Column('col_state', sa.String(length=8), nullable=True),
        sa.Column('container_size', sa.Enum('SIZE_20', 'SIZE_40', 'SIZE_45', name='rate_container_size'), nullable=True),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('per_unit', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('source', sa.Enum('SHEET', 'MILE_RATE', 'HOURLY_RATE', 'MANUAL', 'IMPORT', name='rate_entry_source'), server_default='SHEET', nullable=False),
        sa.Column('change_reason', sa.String(length=500), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['col_point_id'], ['rate_point.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['col_zone_id'], ['rate_zone.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['team_id', 'rate_sheet_id'], ['rate_sheet.team_id', 'rate_sheet.id'], name='fk_rate_entry_sheet_team_id_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_rate_entry_team_id_id'),
    )
    op.create_index('ix_rate_entry_lookup', 'rate_entry', ['team_id', 'rate_sheet_id', 'col_zone_id', 'container_size', 'effective_from'], unique=False)
    op.create_index('ix_rate_entry_team_active', 'rate_entry', ['team_id', 'is_active'], unique=False)
    op.create_index('ix_rate_entry_team_city', 'rate_entry', ['team_id', 'col_city', 'col_state'], unique=False)
    op.create_index(op.f('ix_rate_entry_team_id'), 'rate_entry', ['team_id'], unique=False)
    op.create_index('ix_rate_entry_team_id_id', 'rate_entry', ['team_id', 'id'], unique=False)
    op.create_index('ix_rate_entry_team_point', 'rate_entry', ['team_id', 'col_point_id'], unique=False)
    op.create_index('ix_rate_entry_team_sheet', 'rate_entry', ['team_id', 'rate_sheet_id'], unique=False)

    op.create_table(
        'rate_entry_history',
        sa.Column('rate_sheet_id', sa.Integer(), nullable=False),
        sa.Column('rate_entry_id', sa.Integer(), nullable=True),
        sa.Column('col_zone_id', sa.Integer(), nullable=True),
        sa.Column('col_point_id', sa.Integer(), nullable=True),
        sa.Column('col_city', sa.String(length=120), nullable=True),
        sa.Column('col_state', sa.String(length=8), nullable=True),
        sa.Column('container_size', sa.Enum('SIZE_20', 'SIZE_40', 'SIZE_45', name='rate_container_size_hist'), nullable=True),
        sa.Column('old_amount', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('new_amount', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('old_per_unit', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('new_per_unit', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('action', sa.Enum('SET', 'CLOSE', 'SUPERSEDE', 'DELETE', name='rate_entry_action'), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['team_id', 'rate_sheet_id'], ['rate_sheet.team_id', 'rate_sheet.id'], name='fk_rate_entry_history_sheet_team_id_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_rate_entry_history_team_id_id'),
    )
    op.create_index(op.f('ix_rate_entry_history_team_id'), 'rate_entry_history', ['team_id'], unique=False)
    op.create_index('ix_rate_entry_history_team_id_id', 'rate_entry_history', ['team_id', 'id'], unique=False)
    op.create_index('ix_rate_entry_history_team_sheet', 'rate_entry_history', ['team_id', 'rate_sheet_id', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema — drop the three tables only."""
    op.drop_index('ix_rate_entry_history_team_sheet', table_name='rate_entry_history')
    op.drop_index('ix_rate_entry_history_team_id_id', table_name='rate_entry_history')
    op.drop_index(op.f('ix_rate_entry_history_team_id'), table_name='rate_entry_history')
    op.drop_table('rate_entry_history')
    op.drop_index('ix_rate_entry_team_sheet', table_name='rate_entry')
    op.drop_index('ix_rate_entry_team_point', table_name='rate_entry')
    op.drop_index('ix_rate_entry_team_id_id', table_name='rate_entry')
    op.drop_index(op.f('ix_rate_entry_team_id'), table_name='rate_entry')
    op.drop_index('ix_rate_entry_team_city', table_name='rate_entry')
    op.drop_index('ix_rate_entry_team_active', table_name='rate_entry')
    op.drop_index('ix_rate_entry_lookup', table_name='rate_entry')
    op.drop_table('rate_entry')
    op.drop_index('ix_rate_sheet_team_updated_at', table_name='rate_sheet')
    op.drop_index('ix_rate_sheet_team_kind', table_name='rate_sheet')
    op.drop_index(op.f('ix_rate_sheet_team_id'), table_name='rate_sheet')
    op.drop_index('ix_rate_sheet_team_group', table_name='rate_sheet')
    op.drop_index('ix_rate_sheet_team_active_id', table_name='rate_sheet')
    op.drop_table('rate_sheet')
