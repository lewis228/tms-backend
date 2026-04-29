"""I-2 v3 테이블에 created_by_user_id / updated_by_user_id 보강.

Base 모델 공통 컬럼이 i1 마이그레이션에서 누락됐다. 이를 6개 v3 테이블에 추가.

Revision ID: i2v3audit00010
Revises: i1container00009
Create Date: 2026-04-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i2v3audit00010"
down_revision: Union[str, None] = "i1container00009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


V3_TABLES = (
    "container_stop",
    "leg_driver_segment",
    "rate_quote",
    "rate_tariff",
    "leg_rate",
    "distance_matrix",
)


def upgrade() -> None:
    for t in V3_TABLES:
        op.add_column(t, sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=True))
        op.add_column(t, sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=True))


def downgrade() -> None:
    for t in V3_TABLES:
        op.drop_column(t, "updated_by_user_id")
        op.drop_column(t, "created_by_user_id")
