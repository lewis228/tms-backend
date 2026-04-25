"""add tracking domain tables

Revision ID: a1b2c3d4e5f6
Revises: 4cbe21b2c5c9
Create Date: 2026-04-06 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '4cbe21b2c5c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # companies
    op.create_table('companies',
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('api_key', sa.String(length=255), nullable=False),
        sa.Column('plan', sa.String(length=20), server_default='free', nullable=False),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_companies_api_key', 'companies', ['api_key'], unique=True)
    op.create_index('ix_companies_email', 'companies', ['email'], unique=False)

    # shipments
    op.create_table('shipments',
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('mbl', sa.String(length=50), nullable=False),
        sa.Column('carrier', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='tracking', nullable=False),
        sa.Column('vessel_name', sa.String(length=255), nullable=True),
        sa.Column('voyage_number', sa.String(length=50), nullable=True),
        sa.Column('pol', sa.String(length=100), nullable=True),
        sa.Column('pod', sa.String(length=100), nullable=True),
        sa.Column('etd', sa.DateTime(timezone=True), nullable=True),
        sa.Column('eta', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confidence', sa.String(length=20), nullable=True),
        sa.Column('tracking_frequency', sa.String(length=50), nullable=True),
        sa.Column('next_scrape_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_shipments_mbl', 'shipments', ['mbl'], unique=True)
    op.create_index('ix_shipments_company_id', 'shipments', ['company_id'], unique=False)
    op.create_index('ix_shipments_status', 'shipments', ['status'], unique=False)
    op.create_index('ix_shipments_next_scrape_at', 'shipments', ['next_scrape_at'], unique=False)

    # containers
    op.create_table('containers',
        sa.Column('shipment_id', sa.Integer(), nullable=False),
        sa.Column('number', sa.String(length=20), nullable=False),
        sa.Column('size_type', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('terminal', sa.String(length=255), nullable=True),
        sa.Column('lfd', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_containers_shipment_id', 'containers', ['shipment_id'], unique=False)
    op.create_index('ix_containers_number', 'containers', ['number'], unique=False)

    # tracking_events
    op.create_table('tracking_events',
        sa.Column('shipment_id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('event_type', sa.String(length=20), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['container_id'], ['containers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tracking_events_shipment_id', 'tracking_events', ['shipment_id'], unique=False)
    op.create_index('ix_tracking_events_container_id', 'tracking_events', ['container_id'], unique=False)
    op.create_index('ix_tracking_events_timestamp', 'tracking_events', ['timestamp'], unique=False)

    # scrape_logs
    op.create_table('scrape_logs',
        sa.Column('shipment_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('result_json', sa.JSON(), nullable=True),
        sa.Column('confidence', sa.String(length=20), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['shipment_id'], ['shipments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scrape_logs_shipment_id', 'scrape_logs', ['shipment_id'], unique=False)
    op.create_index('ix_scrape_logs_scraped_at', 'scrape_logs', ['scraped_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_scrape_logs_scraped_at', table_name='scrape_logs')
    op.drop_index('ix_scrape_logs_shipment_id', table_name='scrape_logs')
    op.drop_table('scrape_logs')

    op.drop_index('ix_tracking_events_timestamp', table_name='tracking_events')
    op.drop_index('ix_tracking_events_container_id', table_name='tracking_events')
    op.drop_index('ix_tracking_events_shipment_id', table_name='tracking_events')
    op.drop_table('tracking_events')

    op.drop_index('ix_containers_number', table_name='containers')
    op.drop_index('ix_containers_shipment_id', table_name='containers')
    op.drop_table('containers')

    op.drop_index('ix_shipments_next_scrape_at', table_name='shipments')
    op.drop_index('ix_shipments_status', table_name='shipments')
    op.drop_index('ix_shipments_company_id', table_name='shipments')
    op.drop_index('uq_shipments_mbl', table_name='shipments')
    op.drop_table('shipments')

    op.drop_index('ix_companies_email', table_name='companies')
    op.drop_index('uq_companies_api_key', table_name='companies')
    op.drop_table('companies')
