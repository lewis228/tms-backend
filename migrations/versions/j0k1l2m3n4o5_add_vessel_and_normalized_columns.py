"""vessels + vessel_positions 테이블 + 컨테이너/이벤트 정규화 컬럼 추가

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-04-22 10:00:00.000000

변경 요지:
- ``vessels`` 전역 마스터 테이블 신규 (MMSI / IMO UNIQUE)
- ``vessel_positions`` 1:1 최신 위치 테이블 신규
- ``ocean_shipments.vessel_id`` FK 컬럼 추가 (SET NULL)
- ``ocean_containers.size_type_code`` / ``physical_status`` 정규화 Enum 컬럼
- ``ocean_container_events.event_type_code`` 정규화 Enum 컬럼

이 마이그레이션 후:
- 기존 ocean_containers 의 raw size_type / status 는 그대로 유지
- 정규화 컬럼은 NULL 인 채로 시작 → 다음 스크래핑 사이클에서 save_tracking_result
  이 normalize_* 로 채움
- 과거 데이터 일괄 채우기는 별도 backfill 스크립트로 (이 파일에서는 하지 않음)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─────────────────────────────────────────────────────────
    # 1) vessels (전역 마스터)
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "vessels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mmsi", sa.String(length=16), nullable=True),
        sa.Column("imo_number", sa.String(length=16), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("flag", sa.String(length=4), nullable=True),
        sa.Column("call_sign", sa.String(length=16), nullable=True),
        sa.Column("length_m", sa.Integer(), nullable=True),
        sa.Column("breadth_m", sa.Integer(), nullable=True),
        sa.Column("gross_tonnage", sa.Integer(), nullable=True),
        sa.Column("vessel_type_code", sa.Integer(), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column(
            "last_resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Base 공통 필드
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mmsi", name="uq_vessels_mmsi"),
        sa.UniqueConstraint("imo_number", name="uq_vessels_imo_number"),
    )
    op.create_index("ix_vessels_mmsi", "vessels", ["mmsi"])
    op.create_index("ix_vessels_imo_number", "vessels", ["imo_number"])
    op.create_index("ix_vessels_name", "vessels", ["name"])

    # ─────────────────────────────────────────────────────────
    # 2) vessel_positions (1:1 최신 위치)
    # ─────────────────────────────────────────────────────────
    op.create_table(
        "vessel_positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vessel_id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("speed_knots", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "heading_degrees", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column("navigation_status", sa.String(length=32), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["vessel_id"],
            ["vessels.id"],
            ondelete="CASCADE",
            name="fk_vessel_positions_vessel_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vessel_id", name="uq_vessel_positions_vessel_id"),
    )

    # ─────────────────────────────────────────────────────────
    # 3) ocean_shipments.vessel_id FK
    # ─────────────────────────────────────────────────────────
    op.add_column(
        "ocean_shipments",
        sa.Column("vessel_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ocean_shipments_vessel_id",
        "ocean_shipments",
        "vessels",
        ["vessel_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_ocean_shipments_team_vessel_id",
        "ocean_shipments",
        ["team_id", "vessel_id"],
    )

    # ─────────────────────────────────────────────────────────
    # 4) ocean_containers 정규화 컬럼
    # ─────────────────────────────────────────────────────────
    op.add_column(
        "ocean_containers",
        sa.Column("size_type_code", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "ocean_containers",
        sa.Column("physical_status", sa.String(length=30), nullable=True),
    )
    op.create_index(
        "ix_ocean_containers_team_size_type_code",
        "ocean_containers",
        ["team_id", "size_type_code"],
    )
    op.create_index(
        "ix_ocean_containers_team_physical_status",
        "ocean_containers",
        ["team_id", "physical_status"],
    )

    # ─────────────────────────────────────────────────────────
    # 5) ocean_container_events 정규화 컬럼
    # ─────────────────────────────────────────────────────────
    op.add_column(
        "ocean_container_events",
        sa.Column("event_type_code", sa.String(length=30), nullable=True),
    )
    op.create_index(
        "ix_ocean_container_events_team_event_type_code",
        "ocean_container_events",
        ["team_id", "event_type_code"],
    )


def downgrade() -> None:
    # events
    op.drop_index(
        "ix_ocean_container_events_team_event_type_code",
        table_name="ocean_container_events",
    )
    op.drop_column("ocean_container_events", "event_type_code")

    # containers
    op.drop_index(
        "ix_ocean_containers_team_physical_status",
        table_name="ocean_containers",
    )
    op.drop_index(
        "ix_ocean_containers_team_size_type_code",
        table_name="ocean_containers",
    )
    op.drop_column("ocean_containers", "physical_status")
    op.drop_column("ocean_containers", "size_type_code")

    # shipments.vessel_id
    op.drop_index(
        "ix_ocean_shipments_team_vessel_id", table_name="ocean_shipments"
    )
    op.drop_constraint(
        "fk_ocean_shipments_vessel_id", "ocean_shipments", type_="foreignkey"
    )
    op.drop_column("ocean_shipments", "vessel_id")

    # vessel_positions + vessels
    op.drop_table("vessel_positions")
    op.drop_index("ix_vessels_name", table_name="vessels")
    op.drop_index("ix_vessels_imo_number", table_name="vessels")
    op.drop_index("ix_vessels_mmsi", table_name="vessels")
    op.drop_table("vessels")
