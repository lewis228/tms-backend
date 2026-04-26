"""add LEG_DOCUMENT to file_domain enum

Revision ID: 1882a14b7386
Revises: 3c1dbafe24d0
Create Date: 2026-04-26 16:01:05.899751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1882a14b7386'
down_revision: Union[str, None] = '3c1dbafe24d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """file_asset.domain ENUM 에 leg_document 값 추가 (driver_mobile 첨부)."""
    # MySQL: ENUM 의 값 변경은 ALTER COLUMN 으로 새 값 포함한 ENUM 재정의.
    op.execute("""
        ALTER TABLE file_asset
        MODIFY COLUMN domain ENUM(
            'user','product','partner','purchase','sales',
            'transaction_temp','inbound','outbound','transfer','adjust',
            'return_inbound','tenant',
            'leg_document'
        ) NOT NULL
    """)


def downgrade() -> None:
    """leg_document 값 제거 (해당 row 가 있으면 실패할 수 있음)."""
    op.execute("""
        ALTER TABLE file_asset
        MODIFY COLUMN domain ENUM(
            'user','product','partner','purchase','sales',
            'transaction_temp','inbound','outbound','transfer','adjust',
            'return_inbound','tenant'
        ) NOT NULL
    """)
