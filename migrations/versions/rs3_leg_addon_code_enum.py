"""leg_addon.code enum 확장 (Layer3 charge event 코드 흡수: STP/DET/DMR/YRD)

Revision ID: rs3_addon_code
Revises: rs2_addon_unify
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'rs3_addon_code'
down_revision: Union[str, None] = 'rs2_addon_unify'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW = ("CHS", "HZM", "OOG", "RFR", "CXM", "LYO", "RSP", "FLT", "TNK", "NGT",
        "WKD", "EGT", "LFT", "PPS", "STP", "DET", "DMR", "YRD")
_OLD = ("CHS", "HZM", "OOG", "RFR", "CXM", "LYO", "RSP", "FLT", "TNK", "NGT",
        "WKD", "EGT", "LFT", "PPS")


def _enum(vals):
    return ",".join(f"'{v}'" for v in vals)


def upgrade() -> None:
    op.execute(f"ALTER TABLE leg_addon MODIFY COLUMN code ENUM({_enum(_NEW)}) NOT NULL")


def downgrade() -> None:
    op.execute(f"ALTER TABLE leg_addon MODIFY COLUMN code ENUM({_enum(_OLD)}) NOT NULL")
