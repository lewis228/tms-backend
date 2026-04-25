"""team-scoped tenancy refactor: composite FKs, team_id on line tables, leftmost team_id indexes

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-04-22 00:00:00.000000

팀 중심 멀티테넌시 아키텍처 정착을 위한 스키마 재구성.

다루는 범위:
  1. ocean_shipments: team FK RESTRICT → CASCADE, mbl 글로벌 unique → (team_id, mbl) 복합 unique,
     UniqueConstraint(team_id, id), 인덱스 전부 team_id-leftmost 재구성
  2. ocean_containers / ocean_tracking_events / ocean_scrape_logs: team_id 컬럼 추가 및 부모에서 backfill,
     단순 FK → 복합 FK `(team_id, shipment_id) → ocean_shipments(team_id, id)`,
     UniqueConstraint(team_id, id), 인덱스 재구성
  3. api_keys: UniqueConstraint(team_id, id), 인덱스 정리
  4. tags: UniqueConstraint(team_id, id), 인덱스 재구성
  5. ocean_shipment_tags: team_id 추가/backfill, 단순 FK → 복합 FK, unique 재구성

운영 DB 에 적용할 때 주의:
  * 모든 라인 테이블은 부모 shipment 의 team_id 로 backfill 됨 — 부모 없는 orphan 이 있으면
    NOT NULL 전환 단계에서 실패한다. 미리 클렌징 필요.
  * 큰 규모 DB 라면 이 파일을 데이터-이행 / 스키마-변경 두 개로 쪼개는 것이 안전.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6g7h8i9j0"
down_revision: Union[str, None] = "d4e5f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # 1) ocean_shipments — team FK RESTRICT → CASCADE, unique/인덱스 재구성
    # ==========================================================================

    # 기존 team FK 제거 (`ocean_shipments_team_fk` — 718c062ccc68 에서 RESTRICT 로 생성)
    op.drop_constraint("ocean_shipments_team_fk", "ocean_shipments", type_="foreignkey")

    # 기존 인덱스/유니크 제거
    op.drop_index("uq_ocean_shipments_mbl", table_name="ocean_shipments")
    op.drop_index("ix_ocean_shipments_team_id", table_name="ocean_shipments")
    op.drop_index("ix_ocean_shipments_status", table_name="ocean_shipments")
    op.drop_index("ix_ocean_shipments_next_scrape_at", table_name="ocean_shipments")

    # 새 FK CASCADE
    op.create_foreign_key(
        "ocean_shipments_team_fk",
        "ocean_shipments", "teams",
        ["team_id"], ["id"],
        ondelete="CASCADE",
    )

    # UniqueConstraint(team_id, id) — 복합 FK 타겟용
    op.create_unique_constraint(
        "uq_ocean_shipments_team_id_id", "ocean_shipments", ["team_id", "id"]
    )
    # 팀당 MBL unique
    op.create_unique_constraint(
        "uq_ocean_shipments_team_mbl", "ocean_shipments", ["team_id", "mbl"]
    )

    # 새 인덱스 — team_id leftmost
    op.create_index(
        "ix_ocean_shipments_team_id_id", "ocean_shipments", ["team_id", "id"]
    )
    op.create_index(
        "ix_ocean_shipments_team_mbl", "ocean_shipments", ["team_id", "mbl"]
    )
    op.create_index(
        "ix_ocean_shipments_team_status", "ocean_shipments", ["team_id", "status"]
    )
    op.create_index(
        "ix_ocean_shipments_team_carrier", "ocean_shipments", ["team_id", "carrier"]
    )
    op.create_index(
        "ix_ocean_shipments_team_next_scrape_at",
        "ocean_shipments",
        ["team_id", "next_scrape_at"],
    )
    # Beat 주기 스캔용 — 팀 무관 전역 인덱스
    op.create_index(
        "ix_ocean_shipments_next_scrape_at",
        "ocean_shipments",
        ["next_scrape_at"],
    )

    # ==========================================================================
    # 2) ocean_containers — team_id 컬럼 추가 + backfill + 복합 FK
    # ==========================================================================

    # team_id 컬럼 추가 (임시 nullable)
    op.add_column(
        "ocean_containers", sa.Column("team_id", sa.Integer(), nullable=True)
    )
    # 부모 shipment 에서 backfill
    op.execute(
        """
        UPDATE ocean_containers c
        JOIN ocean_shipments s ON s.id = c.shipment_id
        SET c.team_id = s.team_id
        """
    )
    # NOT NULL 전환
    op.alter_column(
        "ocean_containers", "team_id",
        existing_type=sa.Integer(), nullable=False,
    )

    # 기존 FK shipment_id → ocean_shipments.id 제거 (이름: ocean_containers_ibfk_1)
    op.drop_constraint("ocean_containers_ibfk_1", "ocean_containers", type_="foreignkey")
    # 기존 인덱스 제거
    op.drop_index("ix_ocean_containers_shipment_id", table_name="ocean_containers")
    op.drop_index("ix_ocean_containers_number", table_name="ocean_containers")

    # team_id → teams.id CASCADE FK (Mixin 이 제공할 DDL 과 동일하게 명시적으로 생성)
    op.create_foreign_key(
        "ocean_containers_team_fk",
        "ocean_containers", "teams",
        ["team_id"], ["id"],
        ondelete="CASCADE",
    )
    # 복합 FK (team_id, shipment_id) → ocean_shipments(team_id, id)
    op.create_foreign_key(
        "fk_ocean_containers_shipment_team_id_id",
        "ocean_containers", "ocean_shipments",
        ["team_id", "shipment_id"], ["team_id", "id"],
        ondelete="CASCADE",
    )
    # 제약/인덱스 재구성
    op.create_unique_constraint(
        "uq_ocean_containers_team_id_id", "ocean_containers", ["team_id", "id"]
    )
    op.create_index(
        "ix_ocean_containers_team_id_id", "ocean_containers", ["team_id", "id"]
    )
    op.create_index(
        "ix_ocean_containers_team_shipment",
        "ocean_containers",
        ["team_id", "shipment_id"],
    )
    op.create_index(
        "ix_ocean_containers_team_number",
        "ocean_containers",
        ["team_id", "number"],
    )

    # ==========================================================================
    # 3) ocean_tracking_events — team_id + 복합 FK (shipment_id, container_id)
    # ==========================================================================

    op.add_column(
        "ocean_tracking_events", sa.Column("team_id", sa.Integer(), nullable=True)
    )
    op.execute(
        """
        UPDATE ocean_tracking_events e
        JOIN ocean_shipments s ON s.id = e.shipment_id
        SET e.team_id = s.team_id
        """
    )
    op.alter_column(
        "ocean_tracking_events", "team_id",
        existing_type=sa.Integer(), nullable=False,
    )

    # 기존 단일 FK 제거 (shipment_id = ibfk_1, container_id = ibfk_2 로 추정)
    op.drop_constraint(
        "ocean_tracking_events_ibfk_1", "ocean_tracking_events", type_="foreignkey"
    )
    op.drop_constraint(
        "ocean_tracking_events_ibfk_2", "ocean_tracking_events", type_="foreignkey"
    )
    op.drop_index(
        "ix_ocean_tracking_events_shipment_id", table_name="ocean_tracking_events"
    )
    op.drop_index(
        "ix_ocean_tracking_events_container_id", table_name="ocean_tracking_events"
    )
    op.drop_index(
        "ix_ocean_tracking_events_timestamp", table_name="ocean_tracking_events"
    )

    # team FK + 복합 FK
    op.create_foreign_key(
        "ocean_tracking_events_team_fk",
        "ocean_tracking_events", "teams",
        ["team_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ocean_tracking_events_shipment_team_id_id",
        "ocean_tracking_events", "ocean_shipments",
        ["team_id", "shipment_id"], ["team_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ocean_tracking_events_container_team_id_id",
        "ocean_tracking_events", "ocean_containers",
        ["team_id", "container_id"], ["team_id", "id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_ocean_tracking_events_team_id_id",
        "ocean_tracking_events",
        ["team_id", "id"],
    )
    op.create_index(
        "ix_ocean_tracking_events_team_id_id",
        "ocean_tracking_events",
        ["team_id", "id"],
    )
    op.create_index(
        "ix_ocean_tracking_events_team_shipment",
        "ocean_tracking_events",
        ["team_id", "shipment_id"],
    )
    op.create_index(
        "ix_ocean_tracking_events_team_container",
        "ocean_tracking_events",
        ["team_id", "container_id"],
    )
    op.create_index(
        "ix_ocean_tracking_events_team_timestamp",
        "ocean_tracking_events",
        ["team_id", "timestamp"],
    )

    # ==========================================================================
    # 4) ocean_scrape_logs — team_id + 복합 FK
    # ==========================================================================

    op.add_column(
        "ocean_scrape_logs", sa.Column("team_id", sa.Integer(), nullable=True)
    )
    op.execute(
        """
        UPDATE ocean_scrape_logs l
        JOIN ocean_shipments s ON s.id = l.shipment_id
        SET l.team_id = s.team_id
        """
    )
    op.alter_column(
        "ocean_scrape_logs", "team_id",
        existing_type=sa.Integer(), nullable=False,
    )

    op.drop_constraint(
        "ocean_scrape_logs_ibfk_1", "ocean_scrape_logs", type_="foreignkey"
    )
    op.drop_index("ix_ocean_scrape_logs_shipment_id", table_name="ocean_scrape_logs")
    op.drop_index("ix_ocean_scrape_logs_scraped_at", table_name="ocean_scrape_logs")

    op.create_foreign_key(
        "ocean_scrape_logs_team_fk",
        "ocean_scrape_logs", "teams",
        ["team_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ocean_scrape_logs_shipment_team_id_id",
        "ocean_scrape_logs", "ocean_shipments",
        ["team_id", "shipment_id"], ["team_id", "id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_ocean_scrape_logs_team_id_id", "ocean_scrape_logs", ["team_id", "id"]
    )
    op.create_index(
        "ix_ocean_scrape_logs_team_id_id", "ocean_scrape_logs", ["team_id", "id"]
    )
    op.create_index(
        "ix_ocean_scrape_logs_team_shipment",
        "ocean_scrape_logs",
        ["team_id", "shipment_id"],
    )
    op.create_index(
        "ix_ocean_scrape_logs_team_scraped_at",
        "ocean_scrape_logs",
        ["team_id", "scraped_at"],
    )

    # ==========================================================================
    # 5) api_keys — UniqueConstraint(team_id, id), 인덱스 정리
    # MySQL 주의: FK 가 사용 중인 인덱스는 바로 drop 불가. 새 복합 인덱스를 먼저
    # 만들어 FK 가 leftmost prefix 로 자동 전환되도록 한 뒤 기존 단일 인덱스 drop.
    # ==========================================================================

    op.create_unique_constraint(
        "uq_api_keys_team_id_id", "api_keys", ["team_id", "id"]
    )
    op.create_index("ix_api_keys_team_id_id", "api_keys", ["team_id", "id"])
    op.create_index("ix_api_keys_team_prefix", "api_keys", ["team_id", "prefix"])
    # 이제 FK 가 새 인덱스를 사용하므로 기존 단일 인덱스 drop 가능
    op.drop_index("ix_api_keys_team_id", table_name="api_keys")
    # ix_api_keys_prefix / uq_api_keys_key 유지 (글로벌 키 unique + prefix 인덱스)

    # ==========================================================================
    # 6) tags — UniqueConstraint(team_id, id), 인덱스 재구성 (api_keys 와 동일 이유)
    # ==========================================================================

    op.create_unique_constraint("uq_tags_team_id_id", "tags", ["team_id", "id"])
    op.create_index("ix_tags_team_id_id", "tags", ["team_id", "id"])
    op.create_index("ix_tags_team_name", "tags", ["team_id", "name"])
    op.drop_index("ix_tags_team_id", table_name="tags")
    # uq_tags_team_name 은 유지

    # ==========================================================================
    # 7) ocean_shipment_tags — team_id 추가 + 복합 FK
    # ==========================================================================

    op.add_column(
        "ocean_shipment_tags", sa.Column("team_id", sa.Integer(), nullable=True)
    )
    op.execute(
        """
        UPDATE ocean_shipment_tags st
        JOIN ocean_shipments s ON s.id = st.shipment_id
        SET st.team_id = s.team_id
        """
    )
    op.alter_column(
        "ocean_shipment_tags", "team_id",
        existing_type=sa.Integer(), nullable=False,
    )

    # 기존 FK 제거 (shipment = ibfk_1, tag = ibfk_2 로 추정)
    op.drop_constraint(
        "ocean_shipment_tags_ibfk_1", "ocean_shipment_tags", type_="foreignkey"
    )
    op.drop_constraint(
        "ocean_shipment_tags_ibfk_2", "ocean_shipment_tags", type_="foreignkey"
    )
    op.drop_index(
        "ix_ocean_shipment_tags_shipment_id", table_name="ocean_shipment_tags"
    )
    op.drop_index("ix_ocean_shipment_tags_tag_id", table_name="ocean_shipment_tags")
    op.drop_constraint(
        "uq_ocean_shipment_tags", "ocean_shipment_tags", type_="unique"
    )

    # team FK + 복합 FK
    op.create_foreign_key(
        "ocean_shipment_tags_team_fk",
        "ocean_shipment_tags", "teams",
        ["team_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ocean_shipment_tags_shipment_team_id_id",
        "ocean_shipment_tags", "ocean_shipments",
        ["team_id", "shipment_id"], ["team_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_ocean_shipment_tags_tag_team_id_id",
        "ocean_shipment_tags", "tags",
        ["team_id", "tag_id"], ["team_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_ocean_shipment_tags_team_id_id",
        "ocean_shipment_tags",
        ["team_id", "id"],
    )
    op.create_unique_constraint(
        "uq_ocean_shipment_tags_team_shipment_tag",
        "ocean_shipment_tags",
        ["team_id", "shipment_id", "tag_id"],
    )
    op.create_index(
        "ix_ocean_shipment_tags_team_id_id",
        "ocean_shipment_tags",
        ["team_id", "id"],
    )
    op.create_index(
        "ix_ocean_shipment_tags_team_shipment",
        "ocean_shipment_tags",
        ["team_id", "shipment_id"],
    )
    op.create_index(
        "ix_ocean_shipment_tags_team_tag",
        "ocean_shipment_tags",
        ["team_id", "tag_id"],
    )


def downgrade() -> None:
    # 역순으로 풀어서 원복. FK 이름이 달라지므로 신중하게 반대 순서로.

    # ── 7) ocean_shipment_tags ────────────────────────────────
    op.drop_index("ix_ocean_shipment_tags_team_tag", table_name="ocean_shipment_tags")
    op.drop_index(
        "ix_ocean_shipment_tags_team_shipment", table_name="ocean_shipment_tags"
    )
    op.drop_index(
        "ix_ocean_shipment_tags_team_id_id", table_name="ocean_shipment_tags"
    )
    op.drop_constraint(
        "uq_ocean_shipment_tags_team_shipment_tag",
        "ocean_shipment_tags",
        type_="unique",
    )
    op.drop_constraint(
        "uq_ocean_shipment_tags_team_id_id", "ocean_shipment_tags", type_="unique"
    )
    op.drop_constraint(
        "fk_ocean_shipment_tags_tag_team_id_id",
        "ocean_shipment_tags",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ocean_shipment_tags_shipment_team_id_id",
        "ocean_shipment_tags",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ocean_shipment_tags_team_fk", "ocean_shipment_tags", type_="foreignkey"
    )
    op.create_foreign_key(
        "ocean_shipment_tags_ibfk_1",
        "ocean_shipment_tags", "ocean_shipments",
        ["shipment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ocean_shipment_tags_ibfk_2",
        "ocean_shipment_tags", "tags",
        ["tag_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_ocean_shipment_tags",
        "ocean_shipment_tags",
        ["shipment_id", "tag_id"],
    )
    op.create_index(
        "ix_ocean_shipment_tags_tag_id", "ocean_shipment_tags", ["tag_id"]
    )
    op.create_index(
        "ix_ocean_shipment_tags_shipment_id",
        "ocean_shipment_tags",
        ["shipment_id"],
    )
    op.drop_column("ocean_shipment_tags", "team_id")

    # ── 6) tags ─────────────────────────────────────────────
    op.drop_index("ix_tags_team_name", table_name="tags")
    op.drop_index("ix_tags_team_id_id", table_name="tags")
    op.drop_constraint("uq_tags_team_id_id", "tags", type_="unique")
    op.create_index("ix_tags_team_id", "tags", ["team_id"])

    # ── 5) api_keys ─────────────────────────────────────────
    op.drop_index("ix_api_keys_team_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_team_id_id", table_name="api_keys")
    op.drop_constraint("uq_api_keys_team_id_id", "api_keys", type_="unique")
    op.create_index("ix_api_keys_team_id", "api_keys", ["team_id"])

    # ── 4) ocean_scrape_logs ────────────────────────────────
    op.drop_index(
        "ix_ocean_scrape_logs_team_scraped_at", table_name="ocean_scrape_logs"
    )
    op.drop_index(
        "ix_ocean_scrape_logs_team_shipment", table_name="ocean_scrape_logs"
    )
    op.drop_index("ix_ocean_scrape_logs_team_id_id", table_name="ocean_scrape_logs")
    op.drop_constraint(
        "uq_ocean_scrape_logs_team_id_id", "ocean_scrape_logs", type_="unique"
    )
    op.drop_constraint(
        "fk_ocean_scrape_logs_shipment_team_id_id",
        "ocean_scrape_logs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ocean_scrape_logs_team_fk", "ocean_scrape_logs", type_="foreignkey"
    )
    op.create_foreign_key(
        "ocean_scrape_logs_ibfk_1",
        "ocean_scrape_logs", "ocean_shipments",
        ["shipment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_ocean_scrape_logs_scraped_at", "ocean_scrape_logs", ["scraped_at"]
    )
    op.create_index(
        "ix_ocean_scrape_logs_shipment_id", "ocean_scrape_logs", ["shipment_id"]
    )
    op.drop_column("ocean_scrape_logs", "team_id")

    # ── 3) ocean_tracking_events ────────────────────────────
    op.drop_index(
        "ix_ocean_tracking_events_team_timestamp", table_name="ocean_tracking_events"
    )
    op.drop_index(
        "ix_ocean_tracking_events_team_container", table_name="ocean_tracking_events"
    )
    op.drop_index(
        "ix_ocean_tracking_events_team_shipment", table_name="ocean_tracking_events"
    )
    op.drop_index(
        "ix_ocean_tracking_events_team_id_id", table_name="ocean_tracking_events"
    )
    op.drop_constraint(
        "uq_ocean_tracking_events_team_id_id",
        "ocean_tracking_events",
        type_="unique",
    )
    op.drop_constraint(
        "fk_ocean_tracking_events_container_team_id_id",
        "ocean_tracking_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ocean_tracking_events_shipment_team_id_id",
        "ocean_tracking_events",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ocean_tracking_events_team_fk", "ocean_tracking_events", type_="foreignkey"
    )
    op.create_foreign_key(
        "ocean_tracking_events_ibfk_1",
        "ocean_tracking_events", "ocean_shipments",
        ["shipment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "ocean_tracking_events_ibfk_2",
        "ocean_tracking_events", "ocean_containers",
        ["container_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_ocean_tracking_events_timestamp",
        "ocean_tracking_events",
        ["timestamp"],
    )
    op.create_index(
        "ix_ocean_tracking_events_container_id",
        "ocean_tracking_events",
        ["container_id"],
    )
    op.create_index(
        "ix_ocean_tracking_events_shipment_id",
        "ocean_tracking_events",
        ["shipment_id"],
    )
    op.drop_column("ocean_tracking_events", "team_id")

    # ── 2) ocean_containers ─────────────────────────────────
    op.drop_index("ix_ocean_containers_team_number", table_name="ocean_containers")
    op.drop_index("ix_ocean_containers_team_shipment", table_name="ocean_containers")
    op.drop_index("ix_ocean_containers_team_id_id", table_name="ocean_containers")
    op.drop_constraint(
        "uq_ocean_containers_team_id_id", "ocean_containers", type_="unique"
    )
    op.drop_constraint(
        "fk_ocean_containers_shipment_team_id_id",
        "ocean_containers",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ocean_containers_team_fk", "ocean_containers", type_="foreignkey"
    )
    op.create_foreign_key(
        "ocean_containers_ibfk_1",
        "ocean_containers", "ocean_shipments",
        ["shipment_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_ocean_containers_number", "ocean_containers", ["number"])
    op.create_index(
        "ix_ocean_containers_shipment_id", "ocean_containers", ["shipment_id"]
    )
    op.drop_column("ocean_containers", "team_id")

    # ── 1) ocean_shipments ──────────────────────────────────
    op.drop_index(
        "ix_ocean_shipments_next_scrape_at", table_name="ocean_shipments"
    )
    op.drop_index(
        "ix_ocean_shipments_team_next_scrape_at", table_name="ocean_shipments"
    )
    op.drop_index("ix_ocean_shipments_team_carrier", table_name="ocean_shipments")
    op.drop_index("ix_ocean_shipments_team_status", table_name="ocean_shipments")
    op.drop_index("ix_ocean_shipments_team_mbl", table_name="ocean_shipments")
    op.drop_index("ix_ocean_shipments_team_id_id", table_name="ocean_shipments")
    op.drop_constraint(
        "uq_ocean_shipments_team_mbl", "ocean_shipments", type_="unique"
    )
    op.drop_constraint(
        "uq_ocean_shipments_team_id_id", "ocean_shipments", type_="unique"
    )
    op.drop_constraint(
        "ocean_shipments_team_fk", "ocean_shipments", type_="foreignkey"
    )
    op.create_foreign_key(
        "ocean_shipments_team_fk",
        "ocean_shipments", "teams",
        ["team_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ocean_shipments_next_scrape_at",
        "ocean_shipments",
        ["next_scrape_at"],
    )
    op.create_index(
        "ix_ocean_shipments_status", "ocean_shipments", ["status"]
    )
    op.create_index(
        "ix_ocean_shipments_team_id", "ocean_shipments", ["team_id"]
    )
    op.create_index(
        "uq_ocean_shipments_mbl", "ocean_shipments", ["mbl"], unique=True
    )
