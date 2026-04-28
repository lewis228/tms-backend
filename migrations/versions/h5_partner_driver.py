"""H-5 customer.kind + carrier 컴플라이언스 + driver 확장

Revision ID: h5partner00005
Revises: h4chassis0004
Create Date: 2026-04-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h5partner00005"
down_revision: Union[str, None] = "h4chassis0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1) customer 확장 ─────────────────────────────────────
    op.add_column(
        "customer",
        sa.Column(
            "kind",
            sa.Enum("CUSTOMER", "CARRIER", "BROKER", "VENDOR", name="partner_kind"),
            server_default="CUSTOMER", nullable=False,
        ),
    )
    op.add_column("customer", sa.Column("mc_number", sa.String(length=32), nullable=True))
    op.add_column("customer", sa.Column("dot_number", sa.String(length=32), nullable=True))
    op.add_column("customer", sa.Column("insurance_expires_at", sa.Date(), nullable=True))
    op.add_column("customer", sa.Column("insurance_doc_url", sa.String(length=500), nullable=True))
    op.add_column("customer", sa.Column("w9_doc_url", sa.String(length=500), nullable=True))
    op.add_column("customer", sa.Column("payment_terms_days", sa.Integer(), nullable=True))
    op.create_index("ix_customer_team_kind", "customer", ["team_id", "kind"], unique=False)

    # ── 2) driver 확장 ───────────────────────────────────────
    op.add_column(
        "driver",
        sa.Column(
            "employment_kind",
            sa.Enum(
                "IN_HOUSE", "OWNER_OPERATOR_SOLO", "CARRIER_DRIVER",
                name="employment_kind",
            ),
            server_default="IN_HOUSE", nullable=False,
        ),
    )
    op.add_column("driver", sa.Column("carrier_id", sa.Integer(), nullable=True))
    op.add_column(
        "driver",
        sa.Column(
            "payment_terms_kind",
            sa.Enum(
                "PERCENT_OF_REVENUE", "PER_LEG", "HOURLY", "SALARY",
                name="payment_terms_kind",
            ),
            nullable=True,
        ),
    )
    op.add_column("driver", sa.Column("payment_terms_value", sa.Numeric(14, 4), nullable=True))
    op.add_column("driver", sa.Column("default_truck_id", sa.Integer(), nullable=True))
    op.add_column("driver", sa.Column("default_chassis_id", sa.Integer(), nullable=True))
    op.add_column("driver", sa.Column("license_expires_at", sa.Date(), nullable=True))
    op.add_column("driver", sa.Column("medical_cert_expires_at", sa.Date(), nullable=True))

    op.create_foreign_key(
        "fk_driver_carrier_id", "driver", "customer",
        ["carrier_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_driver_default_truck_id", "driver", "truck",
        ["default_truck_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_driver_default_chassis_id", "driver", "chassis",
        ["default_chassis_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_driver_team_carrier", "driver", ["team_id", "carrier_id"], unique=False)
    op.create_index("ix_driver_team_employment", "driver", ["team_id", "employment_kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_driver_team_employment", table_name="driver")
    op.drop_index("ix_driver_team_carrier", table_name="driver")
    op.drop_constraint("fk_driver_default_chassis_id", "driver", type_="foreignkey")
    op.drop_constraint("fk_driver_default_truck_id", "driver", type_="foreignkey")
    op.drop_constraint("fk_driver_carrier_id", "driver", type_="foreignkey")
    op.drop_column("driver", "medical_cert_expires_at")
    op.drop_column("driver", "license_expires_at")
    op.drop_column("driver", "default_chassis_id")
    op.drop_column("driver", "default_truck_id")
    op.drop_column("driver", "payment_terms_value")
    op.drop_column("driver", "payment_terms_kind")
    op.drop_column("driver", "carrier_id")
    op.drop_column("driver", "employment_kind")

    op.drop_index("ix_customer_team_kind", table_name="customer")
    op.drop_column("customer", "payment_terms_days")
    op.drop_column("customer", "w9_doc_url")
    op.drop_column("customer", "insurance_doc_url")
    op.drop_column("customer", "insurance_expires_at")
    op.drop_column("customer", "dot_number")
    op.drop_column("customer", "mc_number")
    op.drop_column("customer", "kind")
