"""drop legacy v3 cluster (rate_card/quote/tariff/leg_rate/distance_matrix/leg_charge/settlement)

Revision ID: 0b60ce5bffa7
Revises: 077f0ca87594
Create Date: 2026-06-09 18:43:47.392593

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '0b60ce5bffa7'
down_revision: Union[str, None] = '077f0ca87594'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """구 v3 클러스터 테이블 일괄 제거. FK 순서/제약 회피 위해 FK_CHECKS off.

    재설계로 대체: settlement→payroll, leg_charge→leg_layer, leg_rate/rate_card/
    rate_quote/rate_tariff/distance_matrix→payroll.resolve(RateResolver)/invoice.
    """
    # leg.settlement_id (구 settlement FK) 제거
    op.execute("ALTER TABLE leg DROP FOREIGN KEY fk_leg_settlement_id")
    op.execute("ALTER TABLE leg DROP COLUMN settlement_id")
    # 7개 도메인 + settlement 자식 테이블 drop (순서 무관)
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    for _t in (
        "settlement_audit_log", "extra_charge", "settlement",
        "leg_charge", "leg_rate", "rate_card",
        "rate_quote", "rate_tariff", "distance_matrix",
    ):
        op.execute(f"DROP TABLE IF EXISTS {_t}")
    op.execute("SET FOREIGN_KEY_CHECKS=1")


def downgrade() -> None:
    """폐기 클러스터 — 복원하지 않음(재설계로 payroll/invoice/leg_layer 가 대체)."""
    pass
