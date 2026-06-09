"""add rate_point

Revision ID: 374f4dc66d33
Revises: i3drivermob00011
Create Date: 2026-06-09 14:03:44.656189

NOTE: autogenerate 가 기존 모델↔DB 사전 드리프트(enum 값/인덱스 등)도 함께
잡았으나, 이 마이그레이션은 신규 rate_point 테이블 생성만 담당하도록 트리밍했다.
(드리프트는 별도 정리 마이그레이션에서 다룬다 — 재설계 Phase 진행 중 baseline 재정비 예정)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '374f4dc66d33'
down_revision: Union[str, None] = 'i3drivermob00011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create rate_point only."""
    op.create_table(
        'rate_point',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=True),
        sa.Column('point_type', sa.Enum('TERMINAL', 'YARD', name='rate_point_type'), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('latitude', sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column('longitude', sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column('terminal_id', sa.Integer(), nullable=True),
        sa.Column('location_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id'], ['location.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['terminal_id'], ['terminal.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'code', name='uq_rate_point_team_code'),
        sa.UniqueConstraint('team_id', 'id', name='uq_rate_point_team_id_id'),
    )
    op.create_index('ix_rate_point_team_active_id', 'rate_point', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_rate_point_team_id'), 'rate_point', ['team_id'], unique=False)
    op.create_index('ix_rate_point_team_name', 'rate_point', ['team_id', 'name'], unique=False)
    op.create_index('ix_rate_point_team_type', 'rate_point', ['team_id', 'point_type'], unique=False)
    op.create_index('ix_rate_point_team_updated_at', 'rate_point', ['team_id', 'updated_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema — drop rate_point only."""
    op.drop_index('ix_rate_point_team_updated_at', table_name='rate_point')
    op.drop_index('ix_rate_point_team_type', table_name='rate_point')
    op.drop_index('ix_rate_point_team_name', table_name='rate_point')
    op.drop_index(op.f('ix_rate_point_team_id'), table_name='rate_point')
    op.drop_index('ix_rate_point_team_active_id', table_name='rate_point')
    op.drop_table('rate_point')
