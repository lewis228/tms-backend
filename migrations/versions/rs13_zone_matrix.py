"""요율 재설계: Point×Zone → Zone×Zone (from→to) + rate_point 폐기 + leg origin_*

재설계 핵심:
- rate_sheet 슬롯 = (group, kind, move_type, service_type). row_point_id 폐기, kind enum = ZONE/CITY/MILE/HOURLY.
- rate_entry 셀 좌표 = from_zone_id→to_zone_id(ZONE) | from_city/state→to_city/state(CITY).
- rate_entry_history 동일 좌표 스냅샷.
- leg: rate_point_id 제거, origin_zip/city/state 추가(출발 자동채움).
- rate_point 도메인/테이블 완전 폐기.

데이터 폐기 전제(seed 재생성): rate_sheet/rate_entry/rate_entry_history 는 drop 후 새 스키마로 재생성.
leg FK(→rate_point)는 이름이 자동 생성(leg_ibfk_N)이라 inspector 로 동적 drop.

Revision ID: rs13_zone_matrix
Revises: rs12_zip_master
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'rs13_zone_matrix'
down_revision: Union[str, None] = 'rs12_zip_master'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fks_referencing(on_table: str, referred_table: str) -> None:
    """on_table 에서 referred_table 을 참조하는 모든 FK 를 이름으로 drop (이름 자동생성 대응)."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for fk in insp.get_foreign_keys(on_table):
        if fk.get("referred_table") == referred_table and fk.get("name"):
            op.drop_constraint(fk["name"], on_table, type_="foreignkey")


def upgrade() -> None:
    # 1) leg: rate_point_id 제거 + origin_* 추가
    _drop_fks_referencing("leg", "rate_point")
    with op.batch_alter_table("leg") as b:
        b.drop_column("rate_point_id")
        b.add_column(sa.Column("origin_zip", sa.String(length=16), nullable=True))
        b.add_column(sa.Column("origin_city", sa.String(length=120), nullable=True))
        b.add_column(sa.Column("origin_state", sa.String(length=8), nullable=True))

    # 2) 기존 rate 테이블 drop (자식부터) — 데이터 폐기
    op.drop_table("rate_entry_history")
    op.drop_table("rate_entry")
    op.drop_table("rate_sheet")

    # 3) rate_point 테이블 폐기
    op.drop_table("rate_point")

    # 4) rate_sheet 재생성 — (group, kind, move_type, service_type)
    op.create_table(
        "rate_sheet",
        sa.Column("rate_group_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Enum("ZONE", "CITY", "MILE", "HOURLY", name="rate_sheet_kind"), nullable=False),
        sa.Column("move_type", sa.Enum("LOAD", "EMPTY", "NONE", name="rate_move_type"), nullable=True),
        sa.Column("service_type", sa.Enum("LIVE", "DROP", "NONE", name="rate_service_type"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rate_group_id"], ["rate_group.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_rate_sheet_team_id_id"),
        sa.UniqueConstraint("team_id", "rate_group_id", "kind", "move_type", "service_type", name="uq_rate_sheet_slot"),
    )
    op.create_index("ix_rate_sheet_team_active_id", "rate_sheet", ["team_id", "is_active", "id"], unique=False)
    op.create_index("ix_rate_sheet_team_group", "rate_sheet", ["team_id", "rate_group_id"], unique=False)
    op.create_index(op.f("ix_rate_sheet_team_id"), "rate_sheet", ["team_id"], unique=False)
    op.create_index("ix_rate_sheet_team_kind", "rate_sheet", ["team_id", "kind"], unique=False)
    op.create_index("ix_rate_sheet_team_updated_at", "rate_sheet", ["team_id", "updated_at"], unique=False)

    # 5) rate_entry 재생성 — from→to 좌표
    op.create_table(
        "rate_entry",
        sa.Column("rate_sheet_id", sa.Integer(), nullable=False),
        sa.Column("from_zone_id", sa.Integer(), nullable=True),
        sa.Column("to_zone_id", sa.Integer(), nullable=True),
        sa.Column("from_city", sa.String(length=120), nullable=True),
        sa.Column("from_state", sa.String(length=8), nullable=True),
        sa.Column("to_city", sa.String(length=120), nullable=True),
        sa.Column("to_state", sa.String(length=8), nullable=True),
        sa.Column("container_size", sa.Enum("SIZE_20", "SIZE_40", "SIZE_45", name="rate_container_size"), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("per_unit", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source", sa.Enum("SHEET", "MILE_RATE", "HOURLY_RATE", "MANUAL", "IMPORT", name="rate_entry_source"), server_default="SHEET", nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["from_zone_id"], ["rate_zone.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["to_zone_id"], ["rate_zone.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["team_id", "rate_sheet_id"], ["rate_sheet.team_id", "rate_sheet.id"], name="fk_rate_entry_sheet_team_id_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_rate_entry_team_id_id"),
    )
    op.create_index("ix_rate_entry_lookup", "rate_entry", ["team_id", "rate_sheet_id", "from_zone_id", "to_zone_id", "container_size", "effective_from"], unique=False)
    op.create_index("ix_rate_entry_team_active", "rate_entry", ["team_id", "is_active"], unique=False)
    op.create_index("ix_rate_entry_team_city", "rate_entry", ["team_id", "from_city", "from_state", "to_city", "to_state"], unique=False)
    op.create_index(op.f("ix_rate_entry_team_id"), "rate_entry", ["team_id"], unique=False)
    op.create_index("ix_rate_entry_team_id_id", "rate_entry", ["team_id", "id"], unique=False)
    op.create_index("ix_rate_entry_team_sheet", "rate_entry", ["team_id", "rate_sheet_id"], unique=False)

    # 6) rate_entry_history 재생성 — from→to 좌표 스냅샷(FK 없음)
    op.create_table(
        "rate_entry_history",
        sa.Column("rate_sheet_id", sa.Integer(), nullable=False),
        sa.Column("rate_entry_id", sa.Integer(), nullable=True),
        sa.Column("from_zone_id", sa.Integer(), nullable=True),
        sa.Column("to_zone_id", sa.Integer(), nullable=True),
        sa.Column("from_city", sa.String(length=120), nullable=True),
        sa.Column("from_state", sa.String(length=8), nullable=True),
        sa.Column("to_city", sa.String(length=120), nullable=True),
        sa.Column("to_state", sa.String(length=8), nullable=True),
        sa.Column("container_size", sa.Enum("SIZE_20", "SIZE_40", "SIZE_45", name="rate_container_size_hist"), nullable=True),
        sa.Column("old_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("new_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("old_per_unit", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("new_per_unit", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("action", sa.Enum("SET", "CLOSE", "SUPERSEDE", "DELETE", name="rate_entry_action"), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["team_id", "rate_sheet_id"], ["rate_sheet.team_id", "rate_sheet.id"], name="fk_rate_entry_history_sheet_team_id_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_rate_entry_history_team_id_id"),
    )
    op.create_index(op.f("ix_rate_entry_history_team_id"), "rate_entry_history", ["team_id"], unique=False)
    op.create_index("ix_rate_entry_history_team_id_id", "rate_entry_history", ["team_id", "id"], unique=False)
    op.create_index("ix_rate_entry_history_team_sheet", "rate_entry_history", ["team_id", "rate_sheet_id", "created_at"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("rs13_zone_matrix 는 스키마 재작성(데이터 폐기)이라 downgrade 미지원.")
