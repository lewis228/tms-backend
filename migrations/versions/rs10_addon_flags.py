"""leg_addon/delivery_order_addon 청구·정산 분기 플래그 스냅샷

addon 마스터의 is_payable_to_driver / is_billable_to_customer 를 부착 시점에
인스턴스(leg_addon, delivery_order_addon)로 스냅샷 → 정산은 payable 만, 청구는 billable 만 합산.
두 플래그는 독립(정산만/청구만/둘다/둘다아님). 기존 데이터 폐기 가능 전제(default True).

Revision ID: rs10_addon_flags
Revises: rs9_addon_master
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs10_addon_flags'
down_revision: Union[str, None] = 'rs9_addon_master'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("leg_addon", "delivery_order_addon")


def upgrade() -> None:
    for t in _TABLES:
        op.add_column(t, sa.Column(
            "is_payable_to_driver", sa.Boolean(), nullable=False, server_default="1",
        ))
        op.add_column(t, sa.Column(
            "is_billable_to_customer", sa.Boolean(), nullable=False, server_default="1",
        ))


def downgrade() -> None:
    for t in _TABLES:
        op.drop_column(t, "is_billable_to_customer")
        op.drop_column(t, "is_payable_to_driver")
