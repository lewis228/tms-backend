"""init_schema_team_rename

Revision ID: 2422688cd53e
Revises: 
Create Date: 2026-04-27 15:31:14.870974

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2422688cd53e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table('user',
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('password', sa.String(length=255), nullable=True),
    sa.Column('auth_provider', sa.String(length=20), server_default='email', nullable=False),
    sa.Column('oauth_id', sa.String(length=255), nullable=True),
    sa.Column('role', sa.Enum('SUPER_ADMIN', 'ADMIN', 'DISPATCHER', 'DRIVER', name='rolesenum'), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('phone', sa.String(length=30), nullable=True),
    sa.Column('notification_email', sa.String(length=255), nullable=True),
    sa.Column('event_notification_enabled', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('language', sa.String(length=10), server_default='auto', nullable=True),
    sa.Column('is_active_true', sa.Integer(), sa.Computed('CASE WHEN is_active = 1 THEN 1 ELSE NULL END', persisted=False), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('permissions',
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('teams',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deactivated_by', sa.Integer(), nullable=True),
    sa.Column('purge_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('purge_locked', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('onboarding_step1_done', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('onboarding_step2_done', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('onboarding_step3_done', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('onboarding_completed', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('memo', sa.String(length=3000), nullable=True),
    sa.Column('timezone', sa.String(length=50), server_default='Asia/Seoul', nullable=True),
    sa.Column('image_url', sa.String(length=500), nullable=True),
    sa.Column('company_name', sa.String(length=120), nullable=True),
    sa.Column('registration_number', sa.String(length=30), nullable=True),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('representative_name', sa.String(length=80), nullable=True),
    sa.Column('phone_number', sa.String(length=30), nullable=True),
    sa.Column('currency', sa.String(length=10), nullable=True),
    sa.Column('decimal_places', sa.Integer(), server_default='2', nullable=False),
    sa.Column('product_info_display', sa.String(length=30), server_default='all', nullable=True),
    sa.Column('product_info_template', sa.String(length=500), nullable=True),
    sa.Column('excel_product_identification', sa.String(length=30), server_default='sku', nullable=True),
    sa.Column('gs1_gtin_enabled', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('api_key',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('key', sa.String(length=255), nullable=False),
    sa.Column('prefix', sa.String(length=16), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
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
    sa.UniqueConstraint('key', name='uq_api_key_key'),
    sa.UniqueConstraint('team_id', 'id', name='uq_api_key_team_id_id')
    )
    op.create_table('customer',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=True),
    sa.Column('billing_address', sa.String(length=500), nullable=True),
    sa.Column('contact_name', sa.String(length=100), nullable=True),
    sa.Column('contact_email', sa.String(length=128), nullable=True),
    sa.Column('contact_phone', sa.String(length=64), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
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
    sa.UniqueConstraint('team_id', 'code', name='uq_customer_team_code'),
    sa.UniqueConstraint('team_id', 'id', name='uq_customer_team_id_id')
    )
    op.create_table('driver',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('license_number', sa.String(length=64), nullable=True),
    sa.Column('license_state', sa.String(length=8), nullable=True),
    sa.Column('truck_number', sa.String(length=32), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
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
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'id', name='uq_driver_team_id_id'),
    sa.UniqueConstraint('team_id', 'truck_number', name='uq_driver_team_truck'),
    sa.UniqueConstraint('team_id', 'user_id', name='uq_driver_team_user')
    )
    op.create_table('file_asset',
    sa.Column('team_id', sa.Integer(), nullable=True),
    sa.Column('domain', sa.Enum('USER', 'PRODUCT', 'PARTNER', 'PURCHASE', 'SALES', 'TRANSACTION_TEMP', 'INBOUND', 'OUTBOUND', 'TRANSFER', 'ADJUST', 'RETURN_INBOUND', 'TEAM', 'LEG_DOCUMENT', name='file_domain'), nullable=False),
    sa.Column('object_id', sa.Integer(), nullable=False),
    sa.Column('subdir', sa.String(length=50), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('size', sa.BigInteger(), nullable=False),
    sa.Column('mime', sa.String(length=128), nullable=False),
    sa.Column('is_public', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('logical_path', sa.String(length=512), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'id', name='uq_file_asset_team_id_id')
    )
    op.create_table('notification',
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('channel', sa.Enum('PUSH', 'EMAIL', 'SMS', 'WEBHOOK', name='notification_channel'), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'SENT', 'FAILED', 'DELIVERED', name='notification_status'), server_default='PENDING', nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('payload', sa.JSON(), nullable=True),
    sa.Column('is_read', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
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
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'id', name='uq_notification_team_id_id')
    )
    op.create_table('permission_groups',
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('is_system', sa.Boolean(), nullable=False),
    sa.Column('system_key', sa.String(length=20), nullable=True),
    sa.Column('version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('excluded_attribute_ids', sa.JSON(), nullable=True),
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
    sa.UniqueConstraint('team_id', 'id', name='uq_permission_groups_team_id_id'),
    sa.UniqueConstraint('team_id', 'system_key', name='uq_permgroup_system_key')
    )
    op.create_table('rate_setting',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('rate_type', sa.Enum('FLAT_RATE', 'PERCENTAGE', 'PER_MILE', name='rate_type'), nullable=False),
    sa.Column('flat_amount', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('rate_percent', sa.Numeric(precision=7, scale=4), nullable=True),
    sa.Column('rate_per_mile', sa.Numeric(precision=14, scale=4), nullable=True),
    sa.Column('effective_date', sa.Date(), nullable=False),
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
    sa.UniqueConstraint('team_id', 'id', name='uq_rate_setting_team_id_id')
    )
    op.create_table('terminal',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=True),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('latitude', sa.Numeric(precision=10, scale=7), nullable=True),
    sa.Column('longitude', sa.Numeric(precision=10, scale=7), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
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
    sa.UniqueConstraint('team_id', 'code', name='uq_terminal_team_code'),
    sa.UniqueConstraint('team_id', 'id', name='uq_terminal_team_id_id')
    )
    op.create_table('vessel',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('imo_number', sa.String(length=16), nullable=True),
    sa.Column('line', sa.String(length=100), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
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
    sa.UniqueConstraint('team_id', 'id', name='uq_vessel_team_id_id'),
    sa.UniqueConstraint('team_id', 'imo_number', name='uq_vessel_team_imo')
    )
    op.create_table('location',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.Enum('YARD', 'CUSTOMER', 'PORT', 'OTHER', name='location_kind'), server_default='YARD', nullable=False),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('latitude', sa.Numeric(precision=10, scale=7), nullable=True),
    sa.Column('longitude', sa.Numeric(precision=10, scale=7), nullable=True),
    sa.Column('customer_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'id', name='uq_location_team_id_id')
    )
    op.create_table('location_ping',
    sa.Column('driver_id', sa.Integer(), nullable=False),
    sa.Column('latitude', sa.Numeric(precision=10, scale=7), nullable=False),
    sa.Column('longitude', sa.Numeric(precision=10, scale=7), nullable=False),
    sa.Column('speed_kmh', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('heading_deg', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('accuracy_m', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
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
    sa.UniqueConstraint('team_id', 'id', name='uq_location_ping_team_id_id')
    )
    op.create_table('push_token',
    sa.Column('driver_id', sa.Integer(), nullable=False),
    sa.Column('platform', sa.String(length=16), nullable=False),
    sa.Column('token', sa.String(length=512), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
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
    sa.UniqueConstraint('driver_id', 'platform', 'token', name='uq_push_token_driver_platform_token'),
    sa.UniqueConstraint('team_id', 'id', name='uq_push_token_team_id_id')
    )
    op.create_table('permission_group_permissions',
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('permission_id', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['team_id', 'group_id'], ['permission_groups.team_id', 'permission_groups.id'], name='fk_pgperm_group_team_id_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'group_id', 'permission_id', name='uq_pgperm_team_group_perm'),
    sa.UniqueConstraint('team_id', 'id', name='uq_pgperm_team_id_id')
    )
    op.create_table('user_team',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('permission_group_id', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['permission_group_id'], ['permission_groups.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'team_id', name='uq_user_team')
    )
    op.create_table('delivery_order',
    sa.Column('status', sa.Enum('PLANNING', 'DISPATCHED', 'YARD_STAGED', 'FINAL_DELIVERY', 'EMPTY_STAGED', 'COMPLETED', name='delivery_status'), server_default='PLANNING', nullable=False),
    sa.Column('direction', sa.Enum('IMPORT', 'EXPORT', name='shipment_direction'), nullable=False),
    sa.Column('bl_number', sa.String(length=64), nullable=True),
    sa.Column('booking_number', sa.String(length=64), nullable=True),
    sa.Column('reference', sa.String(length=120), nullable=True),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('terminal_id', sa.Integer(), nullable=True),
    sa.Column('vessel_id', sa.Integer(), nullable=True),
    sa.Column('delivery_location_id', sa.Integer(), nullable=True),
    sa.Column('return_location_id', sa.Integer(), nullable=True),
    sa.Column('container_number', sa.String(length=11), nullable=True),
    sa.Column('container_size', sa.Enum('SIZE_20GP', 'SIZE_40GP', 'SIZE_40HC', 'SIZE_40OT', 'SIZE_45HC', 'SIZE_20RF', 'SIZE_40RF', name='container_size'), nullable=True),
    sa.Column('container_type', sa.String(length=32), nullable=True),
    sa.Column('chassis_number', sa.String(length=32), nullable=True),
    sa.Column('eta', sa.DateTime(timezone=True), nullable=True),
    sa.Column('pickup_appointment', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivery_appointment', sa.DateTime(timezone=True), nullable=True),
    sa.Column('return_appointment', sa.DateTime(timezone=True), nullable=True),
    sa.Column('demurrage_lfd', sa.Date(), nullable=True),
    sa.Column('detention_lfd', sa.Date(), nullable=True),
    sa.Column('empty_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('loaded_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('bl_released', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('pier_pass_paid', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('customs_cleared', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('internal_note', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['delivery_location_id'], ['location.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['return_location_id'], ['location.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['terminal_id'], ['terminal.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vessel_id'], ['vessel.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'id', name='uq_delivery_order_team_id_id')
    )
    op.create_table('leg',
    sa.Column('delivery_order_id', sa.Integer(), nullable=False),
    sa.Column('step', sa.Enum('PLANNING', 'DISPATCHED', 'YARD_STAGED', 'FINAL_DELIVERY', 'EMPTY_STAGED', 'COMPLETED', name='delivery_status'), nullable=False),
    sa.Column('move_type', sa.Enum('LOADED', 'EMPTY', name='move_type'), nullable=False),
    sa.Column('service_type', sa.Enum('LIVE', 'DROP', name='service_type'), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'IN_TRANSIT', 'COMPLETED', 'FAILED', name='leg_status'), server_default='PENDING', nullable=False),
    sa.Column('driver_id', sa.Integer(), nullable=True),
    sa.Column('pickup_location_id', sa.Integer(), nullable=True),
    sa.Column('pickup_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivery_location_id', sa.Integer(), nullable=True),
    sa.Column('delivery_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('arrived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failure_reason', sa.String(length=500), nullable=True),
    sa.Column('storage_days', sa.Integer(), server_default='0', nullable=False),
    sa.Column('is_settled', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('settlement_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['delivery_location_id'], ['location.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['delivery_order_id'], ['delivery_order.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['driver_id'], ['driver.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['pickup_location_id'], ['location.id'], ondelete='SET NULL'),
    # FK leg.settlement_id → settlement.id 는 cycle 회피 위해 별도 add_foreign_key
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'id', name='uq_leg_team_id_id')
    )
    op.create_table('street_turn',
    sa.Column('import_order_id', sa.Integer(), nullable=False),
    sa.Column('export_order_id', sa.Integer(), nullable=False),
    sa.Column('container_number', sa.String(length=11), nullable=False),
    sa.Column('link_type', sa.Enum('AUTO', 'MANUAL', name='street_turn_link_type'), nullable=False),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['export_order_id'], ['delivery_order.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['import_order_id'], ['delivery_order.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('export_order_id', name='uq_street_turn_export'),
    sa.UniqueConstraint('import_order_id', name='uq_street_turn_import'),
    sa.UniqueConstraint('team_id', 'id', name='uq_street_turn_team_id_id')
    )
    op.create_table('settlement',
    sa.Column('leg_id', sa.Integer(), nullable=False),
    sa.Column('settlement_status', sa.Enum('PENDING', 'CALCULATED', 'ADJUSTED', 'APPROVED', name='settlement_status'), server_default='PENDING', nullable=False),
    sa.Column('system_total', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('driver_reported_amount', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('discrepancy', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('has_flag', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('final_amount', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('is_settled', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_by', sa.Integer(), nullable=True),
    sa.Column('unapproved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('unapproved_by', sa.Integer(), nullable=True),
    sa.Column('unapproved_reason', sa.String(length=500), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['approved_by'], ['user.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['leg_id'], ['leg.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['unapproved_by'], ['user.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('leg_id', name='uq_settlement_leg_unique'),
    sa.UniqueConstraint('team_id', 'id', name='uq_settlement_team_id_id')
    )
    op.create_table('extra_charge',
    sa.Column('settlement_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=64), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['settlement_id'], ['settlement.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'id', name='uq_extra_charge_team_id_id')
    )
    op.create_table('settlement_audit_log',
    sa.Column('settlement_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.Enum('CALCULATE', 'ADJUST', 'APPROVE', 'UNAPPROVE', name='settlement_audit_action'), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('before_state', sa.JSON(), nullable=True),
    sa.Column('after_state', sa.JSON(), nullable=True),
    sa.Column('reason', sa.String(length=500), nullable=True),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['user.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['settlement_id'], ['settlement.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_user_id'], ['user.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'id', name='uq_settlement_audit_team_id_id')
    )
    op.create_index('ix_leg_team_active_id', 'leg', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_leg_team_do', 'leg', ['team_id', 'delivery_order_id'], unique=False)
    op.create_index('ix_leg_team_driver', 'leg', ['team_id', 'driver_id'], unique=False)
    op.create_index(op.f('ix_leg_team_id'), 'leg', ['team_id'], unique=False)
    op.create_index('ix_leg_team_pickup', 'leg', ['team_id', 'pickup_date'], unique=False)
    op.create_index('ix_leg_team_status', 'leg', ['team_id', 'status'], unique=False)
    op.create_index('ix_leg_team_updated_at', 'leg', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_settlement_team_active_id', 'settlement', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_settlement_team_has_flag', 'settlement', ['team_id', 'has_flag'], unique=False)
    op.create_index(op.f('ix_settlement_team_id'), 'settlement', ['team_id'], unique=False)
    op.create_index('ix_settlement_team_status', 'settlement', ['team_id', 'settlement_status'], unique=False)
    op.create_index('ix_settlement_team_updated_at', 'settlement', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_user_auth_provider', 'user', ['auth_provider'], unique=False)
    op.create_index('ix_user_email', 'user', ['email'], unique=False)
    op.create_index('uq_user_email_active_true', 'user', ['email', 'is_active_true'], unique=True)
    op.create_index('uq_user_oauth_active', 'user', ['auth_provider', 'oauth_id', 'is_active_true'], unique=True)
    op.create_index('ix_permissions_category', 'permissions', ['category'], unique=False)
    op.create_index(op.f('ix_permissions_code'), 'permissions', ['code'], unique=True)
    op.create_index(op.f('ix_teams_purge_at'), 'teams', ['purge_at'], unique=False)
    op.create_index('ix_api_key_prefix', 'api_key', ['prefix'], unique=False)
    op.create_index('ix_api_key_team_active_id', 'api_key', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_api_key_team_id'), 'api_key', ['team_id'], unique=False)
    op.create_index('ix_api_key_team_prefix', 'api_key', ['team_id', 'prefix'], unique=False)
    op.create_index('ix_customer_team_active_id', 'customer', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_customer_team_id'), 'customer', ['team_id'], unique=False)
    op.create_index('ix_customer_team_name', 'customer', ['team_id', 'name'], unique=False)
    op.create_index('ix_customer_team_updated_at', 'customer', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_driver_team_active_id', 'driver', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_driver_team_id'), 'driver', ['team_id'], unique=False)
    op.create_index('ix_driver_team_updated_at', 'driver', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_driver_team_user', 'driver', ['team_id', 'user_id'], unique=False)
    op.create_index('ix_extra_charge_team_active_id', 'extra_charge', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_extra_charge_team_id'), 'extra_charge', ['team_id'], unique=False)
    op.create_index('ix_extra_charge_team_settlement', 'extra_charge', ['team_id', 'settlement_id'], unique=False)
    op.create_index('ix_extra_charge_team_type', 'extra_charge', ['team_id', 'type'], unique=False)
    op.create_index('ix_file_asset_domain_obj', 'file_asset', ['domain', 'object_id'], unique=False)
    op.create_index('ix_file_asset_logical_path', 'file_asset', ['logical_path'], unique=False)
    op.create_index(op.f('ix_file_asset_object_id'), 'file_asset', ['object_id'], unique=False)
    op.create_index('ix_file_asset_team_domain_obj', 'file_asset', ['team_id', 'domain', 'object_id'], unique=False)
    op.create_index(op.f('ix_file_asset_team_id'), 'file_asset', ['team_id'], unique=False)
    op.create_index('ix_file_asset_team_id_id', 'file_asset', ['team_id', 'id'], unique=False)
    op.create_index('ix_file_asset_team_subdir', 'file_asset', ['team_id', 'subdir'], unique=False)
    op.create_index('ix_notification_team_active_id', 'notification', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_notification_team_created_at', 'notification', ['team_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_notification_team_id'), 'notification', ['team_id'], unique=False)
    op.create_index('ix_notification_team_status', 'notification', ['team_id', 'status'], unique=False)
    op.create_index('ix_notification_team_user_read', 'notification', ['team_id', 'user_id', 'is_read'], unique=False)
    op.create_index(op.f('ix_permission_groups_team_id'), 'permission_groups', ['team_id'], unique=False)
    op.create_index('ix_permission_groups_team_id_id', 'permission_groups', ['team_id', 'id'], unique=False)
    op.create_index('ix_permission_groups_team_is_system', 'permission_groups', ['team_id', 'is_system'], unique=False)
    op.create_index('ix_permission_groups_team_name', 'permission_groups', ['team_id', 'name'], unique=False)
    op.create_index('ix_permission_groups_team_updated_at', 'permission_groups', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_rate_setting_team_active_id', 'rate_setting', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_rate_setting_team_effective', 'rate_setting', ['team_id', 'effective_date'], unique=False)
    op.create_index(op.f('ix_rate_setting_team_id'), 'rate_setting', ['team_id'], unique=False)
    op.create_index('ix_rate_setting_team_name', 'rate_setting', ['team_id', 'name'], unique=False)
    op.create_index('ix_rate_setting_team_updated_at', 'rate_setting', ['team_id', 'updated_at'], unique=False)
    op.create_index(op.f('ix_settlement_audit_log_team_id'), 'settlement_audit_log', ['team_id'], unique=False)
    op.create_index('ix_settlement_audit_team_action', 'settlement_audit_log', ['team_id', 'action'], unique=False)
    op.create_index('ix_settlement_audit_team_active_id', 'settlement_audit_log', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_settlement_audit_team_created_at', 'settlement_audit_log', ['team_id', 'created_at'], unique=False)
    op.create_index('ix_settlement_audit_team_settlement', 'settlement_audit_log', ['team_id', 'settlement_id'], unique=False)
    op.create_index('ix_terminal_team_active_id', 'terminal', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_terminal_team_id'), 'terminal', ['team_id'], unique=False)
    op.create_index('ix_terminal_team_name', 'terminal', ['team_id', 'name'], unique=False)
    op.create_index('ix_terminal_team_updated_at', 'terminal', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_vessel_team_active_id', 'vessel', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index(op.f('ix_vessel_team_id'), 'vessel', ['team_id'], unique=False)
    op.create_index('ix_vessel_team_name', 'vessel', ['team_id', 'name'], unique=False)
    op.create_index('ix_vessel_team_updated_at', 'vessel', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_location_team_active_id', 'location', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_location_team_customer', 'location', ['team_id', 'customer_id'], unique=False)
    op.create_index(op.f('ix_location_team_id'), 'location', ['team_id'], unique=False)
    op.create_index('ix_location_team_kind', 'location', ['team_id', 'kind'], unique=False)
    op.create_index('ix_location_team_name', 'location', ['team_id', 'name'], unique=False)
    op.create_index('ix_location_team_updated_at', 'location', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_location_ping_team_active_id', 'location_ping', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_location_ping_team_driver_time', 'location_ping', ['team_id', 'driver_id', 'occurred_at'], unique=False)
    op.create_index(op.f('ix_location_ping_team_id'), 'location_ping', ['team_id'], unique=False)
    op.create_index(op.f('ix_permission_group_permissions_group_id'), 'permission_group_permissions', ['group_id'], unique=False)
    op.create_index(op.f('ix_permission_group_permissions_permission_id'), 'permission_group_permissions', ['permission_id'], unique=False)
    op.create_index(op.f('ix_permission_group_permissions_team_id'), 'permission_group_permissions', ['team_id'], unique=False)
    op.create_index('ix_pgperm_team_group', 'permission_group_permissions', ['team_id', 'group_id'], unique=False)
    op.create_index('ix_pgperm_team_id_id', 'permission_group_permissions', ['team_id', 'id'], unique=False)
    op.create_index('ix_pgperm_team_permission', 'permission_group_permissions', ['team_id', 'permission_id'], unique=False)
    op.create_index('ix_push_token_team_active_id', 'push_token', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_push_token_team_driver', 'push_token', ['team_id', 'driver_id'], unique=False)
    op.create_index(op.f('ix_push_token_team_id'), 'push_token', ['team_id'], unique=False)
    op.create_index('ix_user_teams_permission_group_id', 'user_team', ['permission_group_id'], unique=False)
    op.create_index('ix_user_teams_team_id', 'user_team', ['team_id'], unique=False)
    op.create_index('ix_user_teams_team_updated_at', 'user_team', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_user_teams_user_id', 'user_team', ['user_id'], unique=False)
    op.create_index(op.f('ix_delivery_order_team_id'), 'delivery_order', ['team_id'], unique=False)
    op.create_index('ix_do_team_active_id', 'delivery_order', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_do_team_container', 'delivery_order', ['team_id', 'container_number'], unique=False)
    op.create_index('ix_do_team_customer', 'delivery_order', ['team_id', 'customer_id'], unique=False)
    op.create_index('ix_do_team_demurrage_lfd', 'delivery_order', ['team_id', 'demurrage_lfd'], unique=False)
    op.create_index('ix_do_team_detention_lfd', 'delivery_order', ['team_id', 'detention_lfd'], unique=False)
    op.create_index('ix_do_team_direction', 'delivery_order', ['team_id', 'direction'], unique=False)
    op.create_index('ix_do_team_status', 'delivery_order', ['team_id', 'status'], unique=False)
    op.create_index('ix_do_team_updated_at', 'delivery_order', ['team_id', 'updated_at'], unique=False)
    op.create_index('ix_street_turn_team_active_id', 'street_turn', ['team_id', 'is_active', 'id'], unique=False)
    op.create_index('ix_street_turn_team_container', 'street_turn', ['team_id', 'container_number'], unique=False)
    op.create_index(op.f('ix_street_turn_team_id'), 'street_turn', ['team_id'], unique=False)
    op.create_index('ix_street_turn_team_updated_at', 'street_turn', ['team_id', 'updated_at'], unique=False)
    # ### end Alembic commands ###

    op.create_foreign_key('fk_leg_settlement_id', 'leg', 'settlement', ['settlement_id'], ['id'], ondelete='SET NULL')

def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_street_turn_team_updated_at', table_name='street_turn')
    op.drop_index(op.f('ix_street_turn_team_id'), table_name='street_turn')
    op.drop_index('ix_street_turn_team_container', table_name='street_turn')
    op.drop_index('ix_street_turn_team_active_id', table_name='street_turn')
    op.drop_table('street_turn')
    op.drop_index('ix_do_team_updated_at', table_name='delivery_order')
    op.drop_index('ix_do_team_status', table_name='delivery_order')
    op.drop_index('ix_do_team_direction', table_name='delivery_order')
    op.drop_index('ix_do_team_detention_lfd', table_name='delivery_order')
    op.drop_index('ix_do_team_demurrage_lfd', table_name='delivery_order')
    op.drop_index('ix_do_team_customer', table_name='delivery_order')
    op.drop_index('ix_do_team_container', table_name='delivery_order')
    op.drop_index('ix_do_team_active_id', table_name='delivery_order')
    op.drop_index(op.f('ix_delivery_order_team_id'), table_name='delivery_order')
    op.drop_table('delivery_order')
    op.drop_index('ix_user_teams_user_id', table_name='user_team')
    op.drop_index('ix_user_teams_team_updated_at', table_name='user_team')
    op.drop_index('ix_user_teams_team_id', table_name='user_team')
    op.drop_index('ix_user_teams_permission_group_id', table_name='user_team')
    op.drop_table('user_team')
    op.drop_index(op.f('ix_push_token_team_id'), table_name='push_token')
    op.drop_index('ix_push_token_team_driver', table_name='push_token')
    op.drop_index('ix_push_token_team_active_id', table_name='push_token')
    op.drop_table('push_token')
    op.drop_index('ix_pgperm_team_permission', table_name='permission_group_permissions')
    op.drop_index('ix_pgperm_team_id_id', table_name='permission_group_permissions')
    op.drop_index('ix_pgperm_team_group', table_name='permission_group_permissions')
    op.drop_index(op.f('ix_permission_group_permissions_team_id'), table_name='permission_group_permissions')
    op.drop_index(op.f('ix_permission_group_permissions_permission_id'), table_name='permission_group_permissions')
    op.drop_index(op.f('ix_permission_group_permissions_group_id'), table_name='permission_group_permissions')
    op.drop_table('permission_group_permissions')
    op.drop_index(op.f('ix_location_ping_team_id'), table_name='location_ping')
    op.drop_index('ix_location_ping_team_driver_time', table_name='location_ping')
    op.drop_index('ix_location_ping_team_active_id', table_name='location_ping')
    op.drop_table('location_ping')
    op.drop_index('ix_location_team_updated_at', table_name='location')
    op.drop_index('ix_location_team_name', table_name='location')
    op.drop_index('ix_location_team_kind', table_name='location')
    op.drop_index(op.f('ix_location_team_id'), table_name='location')
    op.drop_index('ix_location_team_customer', table_name='location')
    op.drop_index('ix_location_team_active_id', table_name='location')
    op.drop_table('location')
    op.drop_index('ix_vessel_team_updated_at', table_name='vessel')
    op.drop_index('ix_vessel_team_name', table_name='vessel')
    op.drop_index(op.f('ix_vessel_team_id'), table_name='vessel')
    op.drop_index('ix_vessel_team_active_id', table_name='vessel')
    op.drop_table('vessel')
    op.drop_index('ix_terminal_team_updated_at', table_name='terminal')
    op.drop_index('ix_terminal_team_name', table_name='terminal')
    op.drop_index(op.f('ix_terminal_team_id'), table_name='terminal')
    op.drop_index('ix_terminal_team_active_id', table_name='terminal')
    op.drop_table('terminal')
    op.drop_index('ix_settlement_audit_team_settlement', table_name='settlement_audit_log')
    op.drop_index('ix_settlement_audit_team_created_at', table_name='settlement_audit_log')
    op.drop_index('ix_settlement_audit_team_active_id', table_name='settlement_audit_log')
    op.drop_index('ix_settlement_audit_team_action', table_name='settlement_audit_log')
    op.drop_index(op.f('ix_settlement_audit_log_team_id'), table_name='settlement_audit_log')
    op.drop_table('settlement_audit_log')
    op.drop_index('ix_rate_setting_team_updated_at', table_name='rate_setting')
    op.drop_index('ix_rate_setting_team_name', table_name='rate_setting')
    op.drop_index(op.f('ix_rate_setting_team_id'), table_name='rate_setting')
    op.drop_index('ix_rate_setting_team_effective', table_name='rate_setting')
    op.drop_index('ix_rate_setting_team_active_id', table_name='rate_setting')
    op.drop_table('rate_setting')
    op.drop_index('ix_permission_groups_team_updated_at', table_name='permission_groups')
    op.drop_index('ix_permission_groups_team_name', table_name='permission_groups')
    op.drop_index('ix_permission_groups_team_is_system', table_name='permission_groups')
    op.drop_index('ix_permission_groups_team_id_id', table_name='permission_groups')
    op.drop_index(op.f('ix_permission_groups_team_id'), table_name='permission_groups')
    op.drop_table('permission_groups')
    op.drop_index('ix_notification_team_user_read', table_name='notification')
    op.drop_index('ix_notification_team_status', table_name='notification')
    op.drop_index(op.f('ix_notification_team_id'), table_name='notification')
    op.drop_index('ix_notification_team_created_at', table_name='notification')
    op.drop_index('ix_notification_team_active_id', table_name='notification')
    op.drop_table('notification')
    op.drop_index('ix_file_asset_team_subdir', table_name='file_asset')
    op.drop_index('ix_file_asset_team_id_id', table_name='file_asset')
    op.drop_index(op.f('ix_file_asset_team_id'), table_name='file_asset')
    op.drop_index('ix_file_asset_team_domain_obj', table_name='file_asset')
    op.drop_index(op.f('ix_file_asset_object_id'), table_name='file_asset')
    op.drop_index('ix_file_asset_logical_path', table_name='file_asset')
    op.drop_index('ix_file_asset_domain_obj', table_name='file_asset')
    op.drop_table('file_asset')
    op.drop_index('ix_extra_charge_team_type', table_name='extra_charge')
    op.drop_index('ix_extra_charge_team_settlement', table_name='extra_charge')
    op.drop_index(op.f('ix_extra_charge_team_id'), table_name='extra_charge')
    op.drop_index('ix_extra_charge_team_active_id', table_name='extra_charge')
    op.drop_table('extra_charge')
    op.drop_index('ix_driver_team_user', table_name='driver')
    op.drop_index('ix_driver_team_updated_at', table_name='driver')
    op.drop_index(op.f('ix_driver_team_id'), table_name='driver')
    op.drop_index('ix_driver_team_active_id', table_name='driver')
    op.drop_table('driver')
    op.drop_index('ix_customer_team_updated_at', table_name='customer')
    op.drop_index('ix_customer_team_name', table_name='customer')
    op.drop_index(op.f('ix_customer_team_id'), table_name='customer')
    op.drop_index('ix_customer_team_active_id', table_name='customer')
    op.drop_table('customer')
    op.drop_index('ix_api_key_team_prefix', table_name='api_key')
    op.drop_index(op.f('ix_api_key_team_id'), table_name='api_key')
    op.drop_index('ix_api_key_team_active_id', table_name='api_key')
    op.drop_index('ix_api_key_prefix', table_name='api_key')
    op.drop_table('api_key')
    op.drop_index(op.f('ix_teams_purge_at'), table_name='teams')
    op.drop_table('teams')
    op.drop_index(op.f('ix_permissions_code'), table_name='permissions')
    op.drop_index('ix_permissions_category', table_name='permissions')
    op.drop_table('permissions')
    op.drop_index('uq_user_oauth_active', table_name='user')
    op.drop_index('uq_user_email_active_true', table_name='user')
    op.drop_index('ix_user_email', table_name='user')
    op.drop_index('ix_user_auth_provider', table_name='user')
    op.drop_table('user')
    op.drop_index('ix_settlement_team_updated_at', table_name='settlement')
    op.drop_index('ix_settlement_team_status', table_name='settlement')
    op.drop_index(op.f('ix_settlement_team_id'), table_name='settlement')
    op.drop_index('ix_settlement_team_has_flag', table_name='settlement')
    op.drop_index('ix_settlement_team_active_id', table_name='settlement')
    op.drop_table('settlement')
    op.drop_index('ix_leg_team_updated_at', table_name='leg')
    op.drop_index('ix_leg_team_status', table_name='leg')
    op.drop_index('ix_leg_team_pickup', table_name='leg')
    op.drop_index(op.f('ix_leg_team_id'), table_name='leg')
    op.drop_index('ix_leg_team_driver', table_name='leg')
    op.drop_index('ix_leg_team_do', table_name='leg')
    op.drop_index('ix_leg_team_active_id', table_name='leg')
    op.drop_table('leg')
    # ### end Alembic commands ###
