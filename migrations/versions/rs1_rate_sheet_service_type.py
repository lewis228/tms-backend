"""rate_sheet service_type (Leg 전체 유형: Service Type 별 요율 분리)

Revision ID: rs1_service_type
Revises: 969c61fa6a08
Create Date: 2026-06-10

컨플루언스 'Leg 전체 유형': 같은 From→To·Move Type 이라도 Service Type(Live/Drop/None)
별로 요율표가 다르다. rate_sheet 슬롯에 service_type 차원을 추가한다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs1_service_type'
down_revision: Union[str, None] = '969c61fa6a08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'rate_sheet',
        sa.Column('service_type', sa.Enum('LIVE', 'DROP', 'NONE', name='rate_service_type'), nullable=True),
    )
    # 슬롯 유니크에 service_type 포함 (기존 슬롯은 service_type NULL → MySQL NULL distinct 라 충돌 없음)
    op.drop_constraint('uq_rate_sheet_slot', 'rate_sheet', type_='unique')
    op.create_unique_constraint(
        'uq_rate_sheet_slot', 'rate_sheet',
        ['team_id', 'rate_group_id', 'kind', 'move_type', 'service_type', 'row_point_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_rate_sheet_slot', 'rate_sheet', type_='unique')
    op.create_unique_constraint(
        'uq_rate_sheet_slot', 'rate_sheet',
        ['team_id', 'rate_group_id', 'kind', 'move_type', 'row_point_id'],
    )
    op.drop_column('rate_sheet', 'service_type')
