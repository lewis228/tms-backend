"""add rate_zone

Revision ID: 2eea89deba4c
Revises: 8ae905294a30
Create Date: 2026-06-09 14:30:00.000000

NOTE: autogenerate 가 기존 모델↔DB 사전 드리프트도 함께 잡았으나, 이 마이그레이션은
신규 rate_zone / rate_zone_member 생성만 담당하도록 트리밍했다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2eea89deba4c'
down_revision: Union[str, None] = '8ae905294a30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create rate_zone + rate_zone_member only."""
    op.create_table(
        'rate_zone',
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=True),
        sa.Column('color', sa.String(length=16), nullable=True),
        sa.Column('geojson', sa.JSON(), nullable=True),
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
        sa.UniqueConstraint('team_id', 'id', name='uq_rate_zone_team_id_id'),
        sa.UniqueConstraint('team_id', 'name', name='uq_rate_zone_team_name'),
    )
    op.create_index('ix_rate_zone_team_active_id', 'rate_zone', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_rate_zone_team_id'), 'rate_zone', ['team_id'], unique=False)
    op.create_index('ix_rate_zone_team_name', 'rate_zone', ['team_id', 'name'], unique=False)
    op.create_index('ix_rate_zone_team_updated_at', 'rate_zone', ['team_id', 'updated_at'], unique=False)

    op.create_table(
        'rate_zone_member',
        sa.Column('zone_id', sa.Integer(), nullable=False),
        sa.Column('zip_code', sa.String(length=16), nullable=True),
        sa.Column('city', sa.String(length=120), nullable=True),
        sa.Column('state', sa.String(length=8), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['team_id', 'zone_id'], ['rate_zone.team_id', 'rate_zone.id'], name='fk_rate_zone_member_zone_team_id_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'id', name='uq_rate_zone_member_team_id_id'),
    )
    op.create_index('ix_rate_zone_member_team_city', 'rate_zone_member', ['team_id', 'city', 'state'], unique=False)
    op.create_index(op.f('ix_rate_zone_member_team_id'), 'rate_zone_member', ['team_id'], unique=False)
    op.create_index('ix_rate_zone_member_team_id_id', 'rate_zone_member', ['team_id', 'id'], unique=False)
    op.create_index('ix_rate_zone_member_team_zip', 'rate_zone_member', ['team_id', 'zip_code'], unique=False)
    op.create_index('ix_rate_zone_member_team_zone', 'rate_zone_member', ['team_id', 'zone_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema — drop rate_zone_member + rate_zone only."""
    op.drop_index('ix_rate_zone_member_team_zone', table_name='rate_zone_member')
    op.drop_index('ix_rate_zone_member_team_zip', table_name='rate_zone_member')
    op.drop_index('ix_rate_zone_member_team_id_id', table_name='rate_zone_member')
    op.drop_index(op.f('ix_rate_zone_member_team_id'), table_name='rate_zone_member')
    op.drop_index('ix_rate_zone_member_team_city', table_name='rate_zone_member')
    op.drop_table('rate_zone_member')
    op.drop_index('ix_rate_zone_team_updated_at', table_name='rate_zone')
    op.drop_index('ix_rate_zone_team_name', table_name='rate_zone')
    op.drop_index(op.f('ix_rate_zone_team_id'), table_name='rate_zone')
    op.drop_index('ix_rate_zone_team_active_id', table_name='rate_zone')
    op.drop_table('rate_zone')
