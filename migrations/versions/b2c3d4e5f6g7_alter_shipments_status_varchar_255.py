"""alter shipments status varchar 20 to 255

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-06 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'shipments',
        'status',
        existing_type=sa.String(length=20),
        type_=sa.String(length=255),
        existing_nullable=False,
        existing_server_default='tracking',
    )


def downgrade() -> None:
    op.alter_column(
        'shipments',
        'status',
        existing_type=sa.String(length=255),
        type_=sa.String(length=20),
        existing_nullable=False,
        existing_server_default='tracking',
    )
