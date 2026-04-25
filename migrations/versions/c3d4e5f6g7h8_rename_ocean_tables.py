"""rename ocean tables with ocean_ prefix

Revision ID: c3d4e5f6g7h8
Revises: 594a98baa02e
Create Date: 2026-04-15 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op


revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = '594a98baa02e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (old_name, new_name) — child tables must be renamed before parents are NOT required
# in MySQL because FK references are updated automatically when the referenced table is renamed.
# We still rename in a stable order.
_RENAMES = [
    ("shipments", "ocean_shipments"),
    ("containers", "ocean_containers"),
    ("tracking_events", "ocean_tracking_events"),
    ("scrape_logs", "ocean_scrape_logs"),
]

# Index renames per table: (table_after_rename, old_index_name, new_index_name)
_INDEX_RENAMES = [
    ("ocean_shipments", "uq_shipments_mbl", "uq_ocean_shipments_mbl"),
    ("ocean_shipments", "ix_shipments_company_id", "ix_ocean_shipments_company_id"),
    ("ocean_shipments", "ix_shipments_status", "ix_ocean_shipments_status"),
    ("ocean_shipments", "ix_shipments_next_scrape_at", "ix_ocean_shipments_next_scrape_at"),
    ("ocean_containers", "ix_containers_shipment_id", "ix_ocean_containers_shipment_id"),
    ("ocean_containers", "ix_containers_number", "ix_ocean_containers_number"),
    ("ocean_tracking_events", "ix_tracking_events_shipment_id", "ix_ocean_tracking_events_shipment_id"),
    ("ocean_tracking_events", "ix_tracking_events_container_id", "ix_ocean_tracking_events_container_id"),
    ("ocean_tracking_events", "ix_tracking_events_timestamp", "ix_ocean_tracking_events_timestamp"),
    ("ocean_scrape_logs", "ix_scrape_logs_shipment_id", "ix_ocean_scrape_logs_shipment_id"),
    ("ocean_scrape_logs", "ix_scrape_logs_scraped_at", "ix_ocean_scrape_logs_scraped_at"),
]


def upgrade() -> None:
    for old, new in _RENAMES:
        op.rename_table(old, new)
    for table, old_idx, new_idx in _INDEX_RENAMES:
        # MySQL: ALTER TABLE ... RENAME INDEX old TO new
        op.execute(f"ALTER TABLE `{table}` RENAME INDEX `{old_idx}` TO `{new_idx}`")


def downgrade() -> None:
    for table, old_idx, new_idx in _INDEX_RENAMES:
        op.execute(f"ALTER TABLE `{table}` RENAME INDEX `{new_idx}` TO `{old_idx}`")
    for old, new in reversed(_RENAMES):
        op.rename_table(new, old)
