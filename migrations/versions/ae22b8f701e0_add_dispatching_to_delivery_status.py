"""add DISPATCHING to delivery_status

Revision ID: ae22b8f701e0
Revises: 475da54ea830
Create Date: 2026-06-09 17:33:22.974608

NOTE: MySQL ENUM 변경은 alembic autogenerate 미감지 → 수동.
delivery_status enum 을 쓰는 3개 컬럼(container.status, delivery_order.status, leg.step)에
DISPATCHING 추가(PLANNING 다음). 해당 테이블들은 비어있어 안전.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import mysql

revision: str = 'ae22b8f701e0'
down_revision: Union[str, None] = '475da54ea830'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = mysql.ENUM('PLANNING', 'DISPATCHED', 'YARD_STAGED', 'FINAL_DELIVERY', 'EMPTY_STAGED', 'COMPLETED')
_NEW = mysql.ENUM('PLANNING', 'DISPATCHING', 'DISPATCHED', 'YARD_STAGED', 'FINAL_DELIVERY', 'EMPTY_STAGED', 'COMPLETED')

_TARGETS = [
    ('delivery_order', 'status', False),
    ('container', 'status', False),
    ('leg', 'step', False),
]


def upgrade() -> None:
    for table, col, nullable in _TARGETS:
        op.alter_column(table, col, existing_type=_OLD, type_=_NEW, existing_nullable=nullable)


def downgrade() -> None:
    for table, col, nullable in _TARGETS:
        op.alter_column(table, col, existing_type=_NEW, type_=_OLD, existing_nullable=nullable)
