"""사이즈 차원 폐기 + addon 기사별 금액 분리 테이블

결정 사항 반영:
1. 컨테이너 사이즈는 정산 금액에 영향 없음 → rate_entry/_history 의 container_size 제거,
   rate_multiplier(사이즈 배율) 도메인 통폐기.
2. addon 기사별 금액 차등을 마스터 혼합(driver_id 컬럼)에서 분리 테이블(addon_driver_rate)로:
   마스터 = 순수 카탈로그(uq team+code), 기사별 행 = 금액(amount/percent)만 override.

데이터 폐기 전제(seed 재생성): addon 의 기존 driver override 행은 삭제 후 새 테이블로.

Revision ID: rs14_drop_size_addon_rate
Revises: rs13_zone_matrix
Create Date: 2026-06-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs14_drop_size_addon_rate'
down_revision: Union[str, None] = 'rs13_zone_matrix'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fks_referencing(on_table: str, referred_table: str) -> None:
    """on_table 에서 referred_table 을 참조하는 모든 FK 를 이름으로 drop (자동생성 이름 대응)."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for fk in insp.get_foreign_keys(on_table):
        if fk.get("referred_table") == referred_table and fk.get("name"):
            op.drop_constraint(fk["name"], on_table, type_="foreignkey")


def upgrade() -> None:
    # ── 1) rate_entry / rate_entry_history: container_size 제거 ──
    op.drop_index("ix_rate_entry_lookup", table_name="rate_entry")
    op.drop_column("rate_entry", "container_size")
    op.create_index(
        "ix_rate_entry_lookup", "rate_entry",
        ["team_id", "rate_sheet_id", "from_zone_id", "to_zone_id", "effective_from"],
        unique=False,
    )
    op.drop_column("rate_entry_history", "container_size")

    # ── 2) rate_multiplier 테이블 폐기 ──
    op.drop_table("rate_multiplier")

    # ── 3) addon: driver_id 혼합 구조 폐기 → 순수 카탈로그 ──
    # 기존 driver override 행 삭제(데이터 폐기 전제 — uq(team,code) 충돌 방지)
    op.execute("DELETE FROM addon WHERE driver_id IS NOT NULL")
    _drop_fks_referencing("addon", "driver")
    op.drop_constraint("uq_addon_code_driver", "addon", type_="unique")
    op.drop_index("ix_addon_team_driver", table_name="addon")
    # 모델에서 제거된 보조 인덱스 정리(ix_addon_team_code 는 uq 로 대체)
    op.drop_index("ix_addon_team_code", table_name="addon")
    op.drop_column("addon", "driver_id")
    op.create_unique_constraint("uq_addon_team_code", "addon", ["team_id", "code"])

    # ── 4) addon_driver_rate 생성 (기사별 금액 override 라인) ──
    op.create_table(
        "addon_driver_rate",
        sa.Column("addon_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("percent", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["driver_id"], ["driver.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id", "addon_id"], ["addon.team_id", "addon.id"],
                                name="fk_addon_driver_rate_addon_team_id_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_addon_driver_rate_team_id_id"),
        sa.UniqueConstraint("team_id", "addon_id", "driver_id", name="uq_addon_driver_rate"),
    )
    op.create_index(op.f("ix_addon_driver_rate_team_id"), "addon_driver_rate", ["team_id"], unique=False)
    op.create_index("ix_addon_driver_rate_team_id_id", "addon_driver_rate", ["team_id", "id"], unique=False)
    op.create_index("ix_addon_driver_rate_team_addon", "addon_driver_rate", ["team_id", "addon_id"], unique=False)
    op.create_index("ix_addon_driver_rate_team_driver", "addon_driver_rate", ["team_id", "driver_id"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("rs14 는 스키마 재작성(데이터 폐기)이라 downgrade 미지원.")
