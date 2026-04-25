"""merge company into team, add api_keys, team_id on shipments

Revision ID: 718c062ccc68
Revises: c3d4e5f6g7h8
Create Date: 2026-04-19 12:26:50.300821
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = '718c062ccc68'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _col_exists(table: str, col: str) -> bool:
    return any(c['name'] == col for c in _insp().get_columns(table))


def _index_exists(table: str, idx: str) -> bool:
    return any(i['name'] == idx for i in _insp().get_indexes(table))


def _fk_exists(table: str, fk: str) -> bool:
    return any(f['name'] == fk for f in _insp().get_foreign_keys(table))


def _table_exists(table: str) -> bool:
    return table in _insp().get_table_names()


# Manually reordered from the autogenerate output so FK dependencies resolve
# cleanly on MySQL:
#   1. Extend `teams` with email/plan (needed as target of new shipment FK).
#   2. Flip `ocean_shipments.company_id` FK → `team_id` FK BEFORE dropping
#      `companies`, otherwise InnoDB rejects the DROP.
#   3. Drop `companies`.
#   4. Create `api_keys` table (depends on `teams` existing).


def upgrade() -> None:
    # ── 1) Extend teams ───────────────────────────────────────
    if not _col_exists('teams', 'email'):
        op.add_column('teams', sa.Column('email', sa.String(length=255), nullable=True))
    if not _col_exists('teams', 'plan'):
        op.add_column(
            'teams',
            sa.Column('plan', sa.String(length=20), server_default='free', nullable=False),
        )

    # ── 2) Repoint ocean_shipments FK company_id → team_id ───
    if _col_exists('ocean_shipments', 'company_id'):
        if _fk_exists('ocean_shipments', 'ocean_shipments_ibfk_1'):
            op.drop_constraint('ocean_shipments_ibfk_1', 'ocean_shipments', type_='foreignkey')
        if _index_exists('ocean_shipments', 'ix_ocean_shipments_company_id'):
            op.drop_index('ix_ocean_shipments_company_id', table_name='ocean_shipments')
        op.drop_column('ocean_shipments', 'company_id')

    if not _col_exists('ocean_shipments', 'team_id'):
        op.add_column(
            'ocean_shipments',
            sa.Column('team_id', sa.Integer(), nullable=False),
        )

    if not _index_exists('ocean_shipments', 'ix_ocean_shipments_team_id'):
        op.create_index(
            'ix_ocean_shipments_team_id', 'ocean_shipments', ['team_id'], unique=False,
        )

    if not _fk_exists('ocean_shipments', 'ocean_shipments_team_fk'):
        # Remove orphaned rows whose team_id has no matching teams.id
        op.execute(
            "DELETE FROM ocean_shipments WHERE team_id NOT IN (SELECT id FROM teams)"
        )
        op.create_foreign_key(
            'ocean_shipments_team_fk',
            'ocean_shipments', 'teams',
            ['team_id'], ['id'],
            ondelete='RESTRICT',
        )

    # ── 3) Drop companies ────────────────────────────────────
    if _table_exists('companies'):
        if _index_exists('companies', 'ix_companies_email'):
            op.drop_index('ix_companies_email', table_name='companies')
        if _index_exists('companies', 'uq_companies_api_key'):
            op.drop_index('uq_companies_api_key', table_name='companies')
        op.drop_table('companies')

    # ── 4) Create api_keys ───────────────────────────────────
    if not _table_exists('api_keys'):
        op.create_table(
            'api_keys',
            sa.Column('team_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=80), nullable=False),
            sa.Column('description', sa.String(length=500), nullable=True),
            sa.Column('key', sa.String(length=255), nullable=False),
            sa.Column('prefix', sa.String(length=16), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('now()'),
                nullable=False,
            ),
            sa.Column(
                'updated_at',
                sa.DateTime(timezone=True),
                server_default=sa.text('now()'),
                nullable=False,
            ),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('key'),
        )
        op.create_index('ix_api_keys_prefix', 'api_keys', ['prefix'], unique=False)
        op.create_index('ix_api_keys_team_id', 'api_keys', ['team_id'], unique=False)
        op.create_index('uq_api_keys_key', 'api_keys', ['key'], unique=True)


def downgrade() -> None:
    # Reverse order: api_keys → companies → shipments FK flip → teams columns.
    op.drop_index('uq_api_keys_key', table_name='api_keys')
    op.drop_index('ix_api_keys_team_id', table_name='api_keys')
    op.drop_index('ix_api_keys_prefix', table_name='api_keys')
    op.drop_table('api_keys')

    op.create_table(
        'companies',
        sa.Column('name', mysql.VARCHAR(length=255), nullable=False),
        sa.Column('email', mysql.VARCHAR(length=255), nullable=False),
        sa.Column('api_key', mysql.VARCHAR(length=255), nullable=False),
        sa.Column(
            'plan',
            mysql.VARCHAR(length=20),
            server_default=sa.text("'free'"),
            nullable=False,
        ),
        sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
        sa.Column(
            'is_active',
            mysql.TINYINT(display_width=1),
            server_default=sa.text("'1'"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            'created_at',
            mysql.DATETIME(),
            server_default=sa.text('(now())'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            mysql.DATETIME(),
            server_default=sa.text('(now())'),
            nullable=False,
        ),
        sa.Column(
            'created_by_user_id',
            mysql.INTEGER(),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            'updated_by_user_id',
            mysql.INTEGER(),
            autoincrement=False,
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['user.id'],
            name='companies_ibfk_1', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['updated_by_user_id'], ['user.id'],
            name='companies_ibfk_2', ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_default_charset='utf8mb4',
        mysql_engine='InnoDB',
    )
    op.create_index('uq_companies_api_key', 'companies', ['api_key'], unique=True)
    op.create_index('ix_companies_email', 'companies', ['email'], unique=False)

    op.drop_constraint('ocean_shipments_team_fk', 'ocean_shipments', type_='foreignkey')
    op.drop_index('ix_ocean_shipments_team_id', table_name='ocean_shipments')
    op.drop_column('ocean_shipments', 'team_id')
    op.add_column(
        'ocean_shipments',
        sa.Column(
            'company_id',
            mysql.INTEGER(),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.create_index(
        'ix_ocean_shipments_company_id',
        'ocean_shipments',
        ['company_id'],
        unique=False,
    )
    op.create_foreign_key(
        'ocean_shipments_ibfk_1',
        'ocean_shipments', 'companies',
        ['company_id'], ['id'],
        ondelete='RESTRICT',
    )

    op.drop_column('teams', 'plan')
    op.drop_column('teams', 'email')
