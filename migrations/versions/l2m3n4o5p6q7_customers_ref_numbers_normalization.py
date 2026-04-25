"""normalize customer + ref_numbers; make carrier_id NOT NULL

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-04-23 00:00:00.000000

Changes:
1. Create ``customers`` table (team scoped).
2. Create ``ocean_shipment_ref_numbers`` table (shipment child line).
3. Backfill ``customers`` rows from existing ``ocean_shipments.customer`` strings
   (unique per team_id).
4. Add ``ocean_shipments.customer_id`` FK and populate from backfill.
5. Backfill ``ocean_shipment_ref_numbers`` rows from existing
   ``ocean_shipments.ref_numbers`` JSON arrays.
6. Drop ``ocean_shipments.customer`` and ``ocean_shipments.ref_numbers`` columns.
7. Hard-delete shipments whose ``carrier_id`` is NULL (no viable scraping target)
   and make ``carrier_id`` NOT NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. customers ────────────────────────────────────
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "id", name="uq_customers_team_id_id"),
        sa.UniqueConstraint("team_id", "name", name="uq_customers_team_name"),
    )
    op.create_index(
        "ix_customers_team_id_id", "customers", ["team_id", "id"], unique=False
    )
    op.create_index(
        "ix_customers_team_name", "customers", ["team_id", "name"], unique=False
    )

    # ── 2. ocean_shipment_ref_numbers ───────────────────
    op.create_table(
        "ocean_shipment_ref_numbers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("shipment_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["team_id", "shipment_id"],
            ["ocean_shipments.team_id", "ocean_shipments.id"],
            ondelete="CASCADE",
            name="fk_ocean_shipment_ref_numbers_shipment_team_id_id",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "team_id", "id", name="uq_ocean_shipment_ref_numbers_team_id_id"
        ),
        sa.UniqueConstraint(
            "team_id",
            "shipment_id",
            "value",
            name="uq_ocean_shipment_ref_numbers_team_shipment_value",
        ),
    )
    op.create_index(
        "ix_ocean_shipment_ref_numbers_team_id_id",
        "ocean_shipment_ref_numbers",
        ["team_id", "id"],
        unique=False,
    )
    op.create_index(
        "ix_ocean_shipment_ref_numbers_team_shipment",
        "ocean_shipment_ref_numbers",
        ["team_id", "shipment_id"],
        unique=False,
    )
    op.create_index(
        "ix_ocean_shipment_ref_numbers_team_value",
        "ocean_shipment_ref_numbers",
        ["team_id", "value"],
        unique=False,
    )

    # ── 3. Backfill customers rows from ocean_shipments.customer ────
    # 각 (team_id, 공백 제거된 customer 문자열) 마다 customers row 1개 생성.
    bind.execute(
        sa.text(
            """
            INSERT INTO customers (team_id, name, is_active, created_at, updated_at)
            SELECT DISTINCT s.team_id, TRIM(s.customer), 1, NOW(), NOW()
            FROM ocean_shipments s
            WHERE s.customer IS NOT NULL AND TRIM(s.customer) <> ''
            """
        )
    )

    # ── 4. Add customer_id FK column to ocean_shipments ────────────
    op.add_column(
        "ocean_shipments",
        sa.Column("customer_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ocean_shipments_customer_id",
        "ocean_shipments",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ocean_shipments_team_customer_id",
        "ocean_shipments",
        ["team_id", "customer_id"],
        unique=False,
    )

    # 매칭: (team_id, TRIM(customer) == name) 으로 customer_id 채움.
    bind.execute(
        sa.text(
            """
            UPDATE ocean_shipments s
            JOIN customers c
              ON c.team_id = s.team_id
             AND c.name    = TRIM(s.customer)
            SET s.customer_id = c.id
            WHERE s.customer IS NOT NULL AND TRIM(s.customer) <> ''
            """
        )
    )

    # ── 5. Backfill ref_number rows from ocean_shipments.ref_numbers JSON ──
    # MySQL 8: JSON_TABLE 로 배열 풀어서 각 원소를 row 로 전개.
    bind.execute(
        sa.text(
            """
            INSERT INTO ocean_shipment_ref_numbers
                (team_id, shipment_id, value, is_active, created_at, updated_at)
            SELECT s.team_id, s.id, jt.value, 1, NOW(), NOW()
            FROM ocean_shipments s
            CROSS JOIN JSON_TABLE(
                s.ref_numbers,
                '$[*]' COLUMNS (value VARCHAR(100) PATH '$')
            ) AS jt
            WHERE s.ref_numbers IS NOT NULL
              AND JSON_LENGTH(s.ref_numbers) > 0
              AND jt.value IS NOT NULL
              AND TRIM(jt.value) <> ''
            """
        )
    )

    # ── 6. Drop legacy columns ──────────────────────────
    op.drop_column("ocean_shipments", "customer")
    op.drop_column("ocean_shipments", "ref_numbers")

    # ── 7. carrier_id NOT NULL ──────────────────────────
    # NULL carrier_id 인 shipment 는 스크래핑이 불가능한 상태 — 하드 삭제.
    # CASCADE 로 containers / events / scrape_logs / tag 링크 / ref_numbers 도 정리.
    bind.execute(
        sa.text("DELETE FROM ocean_shipments WHERE carrier_id IS NULL")
    )
    # MySQL 8.0 은 FK 에 걸린 컬럼의 NOT NULL 전환을 거부한다
    # (ER_FK_COLUMN_CANNOT_CHANGE). FK drop → alter → FK 재생성.
    op.drop_constraint(
        "fk_ocean_shipments_carrier_id", "ocean_shipments", type_="foreignkey"
    )
    op.alter_column(
        "ocean_shipments",
        "carrier_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_ocean_shipments_carrier_id",
        "ocean_shipments",
        "carriers",
        ["carrier_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    bind = op.get_bind()

    # carrier_id 되돌리기
    op.alter_column(
        "ocean_shipments",
        "carrier_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 레거시 컬럼 복원
    op.add_column(
        "ocean_shipments",
        sa.Column("customer", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "ocean_shipments",
        sa.Column("ref_numbers", sa.JSON(), nullable=True),
    )

    # customer_id → customer 문자열로 복원
    bind.execute(
        sa.text(
            """
            UPDATE ocean_shipments s
            JOIN customers c ON c.id = s.customer_id
            SET s.customer = c.name
            WHERE s.customer_id IS NOT NULL
            """
        )
    )

    # ref_number row → JSON 배열로 집계 복원
    bind.execute(
        sa.text(
            """
            UPDATE ocean_shipments s
            SET s.ref_numbers = (
                SELECT JSON_ARRAYAGG(r.value)
                FROM ocean_shipment_ref_numbers r
                WHERE r.team_id = s.team_id
                  AND r.shipment_id = s.id
            )
            WHERE EXISTS (
                SELECT 1 FROM ocean_shipment_ref_numbers r
                WHERE r.team_id = s.team_id AND r.shipment_id = s.id
            )
            """
        )
    )

    op.drop_index(
        "ix_ocean_shipments_team_customer_id", table_name="ocean_shipments"
    )
    op.drop_constraint(
        "fk_ocean_shipments_customer_id",
        "ocean_shipments",
        type_="foreignkey",
    )
    op.drop_column("ocean_shipments", "customer_id")

    op.drop_index(
        "ix_ocean_shipment_ref_numbers_team_value",
        table_name="ocean_shipment_ref_numbers",
    )
    op.drop_index(
        "ix_ocean_shipment_ref_numbers_team_shipment",
        table_name="ocean_shipment_ref_numbers",
    )
    op.drop_index(
        "ix_ocean_shipment_ref_numbers_team_id_id",
        table_name="ocean_shipment_ref_numbers",
    )
    op.drop_table("ocean_shipment_ref_numbers")

    op.drop_index("ix_customers_team_name", table_name="customers")
    op.drop_index("ix_customers_team_id_id", table_name="customers")
    op.drop_table("customers")
