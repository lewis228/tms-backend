"""api_keys: drop revoked_at — soft-delete 를 is_active/updated_at 로 통일

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-04-22 12:00:00.000000

``revoked_at`` 은 사실상 ``is_active=False`` + ``updated_at`` 조합으로 대체 가능.
전 도메인 soft-delete 정책을 ``is_active`` 로 단일화하기 위해 컬럼 제거.
회수된 키는 ``is_active=False`` 로 마킹되고 ``updated_at`` 이 회수 시점을 기록한다.

**데이터 이행**: 기존에 ``revoked_at`` 이 NOT NULL 이었던 row 는
``is_active=False`` 로 전환 (아직 revoke 로 도달한 row 가 없다면 no-op).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6g7h8i9j0k1"
down_revision: Union[str, None] = "e5f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 기존 revoked 데이터를 is_active=False 로 옮김
    op.execute(
        """
        UPDATE api_keys
           SET is_active = 0
         WHERE revoked_at IS NOT NULL
        """
    )
    # 2) revoked_at 컬럼 제거
    op.drop_column("api_keys", "revoked_at")


def downgrade() -> None:
    # 컬럼 복원 (데이터는 부분 복원 — is_active=False 인 row 의 revoked_at 을 updated_at 으로 채움)
    op.add_column(
        "api_keys",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE api_keys
           SET revoked_at = updated_at
         WHERE is_active = 0
        """
    )
