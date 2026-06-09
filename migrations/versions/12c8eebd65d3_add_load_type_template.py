"""add load_type_template

Revision ID: 12c8eebd65d3
Revises: e54b61c51195
Create Date: 2026-06-09 14:53:46.508809

NOTE: 신규 load_type_template / load_type_template_step 생성만 — 사전 드리프트 트리밍.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '12c8eebd65d3'
down_revision: Union[str, None] = 'e54b61c51195'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'load_type_template',
        sa.Column('code', sa.String(length=48), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('direction', sa.Enum('IMPORT', 'EXPORT', 'BOTH', name='load_type_direction'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), server_default='0', nullable=False),
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
        sa.UniqueConstraint('team_id', 'code', name='uq_load_type_template_team_code'),
        sa.UniqueConstraint('team_id', 'id', name='uq_load_type_template_team_id_id'),
    )
    op.create_index('ix_load_type_template_team_active_id', 'load_type_template', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_load_type_template_team_direction', 'load_type_template', ['team_id', 'direction'], unique=False)
    op.create_index(op.f('ix_load_type_template_team_id'), 'load_type_template', ['team_id'], unique=False)
    op.create_index('ix_load_type_template_team_updated_at', 'load_type_template', ['team_id', 'updated_at'], unique=False)

    op.create_table(
        'load_type_template_step',
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('from_location_type', sa.Enum('TERMINAL', 'YARD', 'CUSTOMER', name='lt_from_location_type'), nullable=True),
        sa.Column('to_location_type', sa.Enum('TERMINAL', 'YARD', 'CUSTOMER', name='lt_to_location_type'), nullable=True),
        sa.Column('move_type', sa.Enum('LOAD', 'EMPTY', 'NONE', name='lt_move_type'), nullable=False),
        sa.Column('service_type', sa.Enum('LIVE', 'DROP', 'NONE', name='lt_service_type'), nullable=False),
        sa.Column('move_code', sa.Enum('PPU', 'PRE', 'PPL', 'DRP', 'STR', 'TRL', 'RMP', 'OTR', 'ERP', name='lt_move_code'), nullable=True),
        sa.Column('flags', sa.JSON(), nullable=True),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['team_id', 'template_id'], ['load_type_template.team_id', 'load_type_template.id'], name='fk_lt_template_step_template_team_id_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_lt_template_step_team_id_id'),
    )
    op.create_index(op.f('ix_load_type_template_step_team_id'), 'load_type_template_step', ['team_id'], unique=False)
    op.create_index('ix_lt_template_step_team_id_id', 'load_type_template_step', ['team_id', 'id'], unique=False)
    op.create_index('ix_lt_template_step_team_template', 'load_type_template_step', ['team_id', 'template_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_lt_template_step_team_template', table_name='load_type_template_step')
    op.drop_index('ix_lt_template_step_team_id_id', table_name='load_type_template_step')
    op.drop_index(op.f('ix_load_type_template_step_team_id'), table_name='load_type_template_step')
    op.drop_table('load_type_template_step')
    op.drop_index('ix_load_type_template_team_updated_at', table_name='load_type_template')
    op.drop_index(op.f('ix_load_type_template_team_id'), table_name='load_type_template')
    op.drop_index('ix_load_type_template_team_direction', table_name='load_type_template')
    op.drop_index('ix_load_type_template_team_active_id', table_name='load_type_template')
    op.drop_table('load_type_template')
