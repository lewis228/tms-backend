"""원자(ZIP/CITY) + 존 레이어 + 양방향 사다리 모델

확정 설계(컨플루언스 v12) 반영:
1. 방식 enum ZONE→ZIP (RateMethod / SheetKind) — 존은 방식이 아니라 묶음 레이어.
2. rate_group.inherits_default — 커스텀 그룹의 디폴트 폴백(사다리 ④) 여부.
3. rate_zone.rate_group_id — NULL=팀 공용, 값=그룹 전용 존(해석 시 우선).
4. rate_zone_member: zip_code nullable + city/state 추가 — 도시존(CITY 방식 묶기).
5. rate_entry/_history: from_zip/to_zip 원자 좌표 추가 — 사다리 ①·② 셀.
   (구간 양방향 정규화는 앱 레벨 lane.normalize_cell — 스키마 변경 없음)

데이터 폐기 전제(seed 재생성) — enum UPDATE 는 비어있지 않은 dev DB 대비 보호용.

Revision ID: rs15_zip_zone_layer
Revises: rs14_drop_size_addon_rate
Create Date: 2026-06-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs15_zip_zone_layer'
down_revision: Union[str, None] = 'rs14_drop_size_addon_rate'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) enum ZONE→ZIP (MySQL 3단계: 합집합 enum → 값 치환 → 최종 enum) ──
    op.alter_column(
        "rate_group", "method",
        type_=sa.Enum("ZIP", "ZONE", "CITY", "MILE", "HOURLY", name="rate_method"),
        existing_nullable=False,
    )
    op.execute("UPDATE rate_group SET method='ZIP' WHERE method='ZONE'")
    op.alter_column(
        "rate_group", "method",
        type_=sa.Enum("ZIP", "CITY", "MILE", "HOURLY", name="rate_method"),
        existing_nullable=False,
    )
    op.alter_column(
        "rate_sheet", "kind",
        type_=sa.Enum("ZIP", "ZONE", "CITY", "MILE", "HOURLY", name="rate_sheet_kind"),
        existing_nullable=False,
    )
    op.execute("UPDATE rate_sheet SET kind='ZIP' WHERE kind='ZONE'")
    op.alter_column(
        "rate_sheet", "kind",
        type_=sa.Enum("ZIP", "CITY", "MILE", "HOURLY", name="rate_sheet_kind"),
        existing_nullable=False,
    )

    # ── 2) rate_group.inherits_default ──
    op.add_column(
        "rate_group",
        sa.Column("inherits_default", sa.Boolean(), server_default="1", nullable=False),
    )

    # ── 3) rate_zone.rate_group_id (NULL=팀 공용, 값=그룹 전용) ──
    op.add_column("rate_zone", sa.Column("rate_group_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_rate_zone_rate_group", "rate_zone", "rate_group",
        ["rate_group_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_rate_zone_team_group", "rate_zone", ["team_id", "rate_group_id"])

    # ── 4) rate_zone_member: city 멤버(도시존) 지원 ──
    op.alter_column(
        "rate_zone_member", "zip_code",
        existing_type=sa.String(16), nullable=True,
    )
    op.add_column("rate_zone_member", sa.Column("city", sa.String(120), nullable=True))
    op.add_column("rate_zone_member", sa.Column("state", sa.String(8), nullable=True))
    op.create_index(
        "ix_rate_zone_member_team_city", "rate_zone_member",
        ["team_id", "city", "state"],
    )

    # ── 5) rate_entry / rate_entry_history: zip 원자 좌표 ──
    op.add_column("rate_entry", sa.Column("from_zip", sa.String(16), nullable=True))
    op.add_column("rate_entry", sa.Column("to_zip", sa.String(16), nullable=True))
    op.create_index(
        "ix_rate_entry_team_zip", "rate_entry",
        ["team_id", "rate_sheet_id", "from_zip", "to_zip", "effective_from"],
    )
    op.add_column("rate_entry_history", sa.Column("from_zip", sa.String(16), nullable=True))
    op.add_column("rate_entry_history", sa.Column("to_zip", sa.String(16), nullable=True))


def downgrade() -> None:
    raise NotImplementedError("rs15 는 전방 전용 마이그레이션입니다 (데이터 폐기 전제).")
