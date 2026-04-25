"""ocean_tracking_events → ocean_container_events 리네임 + container_id NOT NULL

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-04-21 12:00:00.000000

모든 트래킹 이벤트는 이제 **반드시 특정 컨테이너에 귀속** 된다. 선박 레벨
이벤트(출항/입항 등) 는 scraping 측 fan-out 로직이 해당 shipment 의 모든
컨테이너로 복제 저장하므로 concept-level 의 "shipment 이벤트" 도 UI 상
각 컨테이너 타임라인에 나타난다.

변경:
  1) 남아 있는 ``container_id IS NULL`` row 전부 삭제 (데이터 정합성 보장)
  2) ``container_id`` 컬럼을 NOT NULL 로 전환
  3) 인덱스/제약/FK 이름을 새 테이블명 prefix 로 rename
  4) 테이블명 ``ocean_tracking_events`` → ``ocean_container_events``
"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_TABLE = "ocean_tracking_events"
NEW_TABLE = "ocean_container_events"

# 인덱스 네이밍: `ix_<table>_<cols>` 규약
OLD_INDEXES = {
    "ix_ocean_tracking_events_team_id_id":      "ix_ocean_container_events_team_id_id",
    "ix_ocean_tracking_events_team_shipment":   "ix_ocean_container_events_team_shipment",
    "ix_ocean_tracking_events_team_container":  "ix_ocean_container_events_team_container",
    "ix_ocean_tracking_events_team_timestamp":  "ix_ocean_container_events_team_timestamp",
}
OLD_UNIQUE = "uq_ocean_tracking_events_team_id_id"
NEW_UNIQUE = "uq_ocean_container_events_team_id_id"

# 복합 FK 네이밍: `fk_<table>_<ref>_<cols>`
OLD_FK_SHIPMENT = "fk_ocean_tracking_events_shipment_team_id_id"
NEW_FK_SHIPMENT = "fk_ocean_container_events_shipment_team_id_id"
OLD_FK_CONTAINER = "fk_ocean_tracking_events_container_team_id_id"
NEW_FK_CONTAINER = "fk_ocean_container_events_container_team_id_id"


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1) container_id IS NULL row 정리 ────────────────────
    # 이 시점의 orphan 이벤트는 fan-out 결과물이 아니라 이전 설계에서
    # "shipment-level" 로 흘러들어간 레거시. 새 스키마에선 의미가 없다.
    bind.execute(
        sa.text(f"DELETE FROM {OLD_TABLE} WHERE container_id IS NULL")
    )

    # ── 2) FK 제약 먼저 drop — MySQL 8.0 은 FK 에 걸린 컬럼의
    #       NOT NULL 전환을 거부한다 (ER_FK_COLUMN_CANNOT_CHANGE).
    op.drop_constraint(OLD_FK_CONTAINER, OLD_TABLE, type_="foreignkey")
    op.drop_constraint(OLD_FK_SHIPMENT, OLD_TABLE, type_="foreignkey")

    # ── 3) container_id NOT NULL 로 alter ────────────────────
    op.alter_column(
        OLD_TABLE,
        "container_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 인덱스는 RENAME INDEX 문이 MySQL 5.7+ 에서 지원됨
    for old_name, new_name in OLD_INDEXES.items():
        bind.execute(sa.text(
            f"ALTER TABLE {OLD_TABLE} RENAME INDEX {old_name} TO {new_name}"
        ))

    # UniqueConstraint 도 인덱스의 일종 — MySQL 에선 RENAME INDEX 로 처리
    bind.execute(sa.text(
        f"ALTER TABLE {OLD_TABLE} RENAME INDEX {OLD_UNIQUE} TO {NEW_UNIQUE}"
    ))

    # ── 4) 테이블 rename ────────────────────────────────────
    op.rename_table(OLD_TABLE, NEW_TABLE)

    # ── 5) 복합 FK 다시 붙이기 (새 이름으로) ─────────────────
    op.create_foreign_key(
        NEW_FK_SHIPMENT,
        NEW_TABLE,
        "ocean_shipments",
        ["team_id", "shipment_id"],
        ["team_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        NEW_FK_CONTAINER,
        NEW_TABLE,
        "ocean_containers",
        ["team_id", "container_id"],
        ["team_id", "id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    bind = op.get_bind()

    # 복합 FK 제거
    op.drop_constraint(NEW_FK_CONTAINER, NEW_TABLE, type_="foreignkey")
    op.drop_constraint(NEW_FK_SHIPMENT, NEW_TABLE, type_="foreignkey")

    # 테이블 원복
    op.rename_table(NEW_TABLE, OLD_TABLE)

    # 인덱스 이름 원복
    for old_name, new_name in OLD_INDEXES.items():
        bind.execute(sa.text(
            f"ALTER TABLE {OLD_TABLE} RENAME INDEX {new_name} TO {old_name}"
        ))
    bind.execute(sa.text(
        f"ALTER TABLE {OLD_TABLE} RENAME INDEX {NEW_UNIQUE} TO {OLD_UNIQUE}"
    ))

    # container_id nullable 로 되돌림
    op.alter_column(
        OLD_TABLE,
        "container_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 원래 이름으로 복합 FK 재부착
    op.create_foreign_key(
        OLD_FK_SHIPMENT,
        OLD_TABLE,
        "ocean_shipments",
        ["team_id", "shipment_id"],
        ["team_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        OLD_FK_CONTAINER,
        OLD_TABLE,
        "ocean_containers",
        ["team_id", "container_id"],
        ["team_id", "id"],
        ondelete="CASCADE",
    )
