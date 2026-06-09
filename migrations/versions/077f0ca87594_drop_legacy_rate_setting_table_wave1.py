"""drop legacy rate_setting table (wave1)

Revision ID: 077f0ca87594
Revises: dfc5c2c9009e
Create Date: 2026-06-09 18:29:54.462729

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '077f0ca87594'
down_revision: Union[str, None] = 'dfc5c2c9009e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """구 v3 rate_setting 테이블 제거(Wave 1). FK 자기참조 인덱스 제약 회피 위해 FK_CHECKS off."""
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    op.execute("DROP TABLE IF EXISTS rate_setting")
    op.execute("SET FOREIGN_KEY_CHECKS=1")


def downgrade() -> None:
    """폐기 테이블 — 복원하지 않음(재설계로 대체)."""
    pass
