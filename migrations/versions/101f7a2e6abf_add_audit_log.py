"""add audit_log

Revision ID: 101f7a2e6abf
Revises: 4544ea70eff1
Create Date: 2026-06-09 15:12:00.000000

NOTE: 신규 audit_log 생성만 — 사전 드리프트 트리밍.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '101f7a2e6abf'
down_revision: Union[str, None] = '4544ea70eff1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('entity_type', sa.String(length=48), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=True),
        sa.Column('before_state', sa.JSON(), nullable=True),
        sa.Column('after_state', sa.JSON(), nullable=True),
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
        sa.UniqueConstraint('team_id', 'id', name='uq_audit_log_team_id_id'),
    )
    op.create_index('ix_audit_log_team_created', 'audit_log', ['team_id', 'created_at'], unique=False)
    op.create_index('ix_audit_log_team_entity', 'audit_log', ['team_id', 'entity_type', 'entity_id', 'id'], unique=False)
    op.create_index(op.f('ix_audit_log_team_id'), 'audit_log', ['team_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_log_team_id'), table_name='audit_log')
    op.drop_index('ix_audit_log_team_entity', table_name='audit_log')
    op.drop_index('ix_audit_log_team_created', table_name='audit_log')
    op.drop_table('audit_log')
