"""I-1 Container-First v3: Stop / DriverSegment / RateQuote / RateTariff / LegRate /
DistanceMatrix + LegCharge.snapshot_unit_amount + ChargeCode boost +
Leg.move_type_v3 / from_stop_id / to_stop_id + Container.work_state +
Team distance/currency labels.

기존 데이터는 보존. 새 컬럼은 모두 nullable 또는 default 부여.

Revision ID: i1container00009
Revises: h8street00008
Create Date: 2026-04-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i1container00009"
down_revision: Union[str, None] = "h8street00008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── ENUM 정의 ─────────────────────────────────────────────
STOP_ROLE = ("ORIGIN", "DELIVERY", "TRANSIT", "TERMINUS")
HANDOVER_REASON = ("TERMINAL_CLOSED", "ACCIDENT", "SHIFT_CHANGE", "OTHER")
CONTAINER_STATE = (
    "DRAFT", "PLANNED", "IN_TRANSIT", "AT_STOP",
    "WAITING_PLAN", "HOLD", "COMPLETED", "CANCELLED",
)
MOVE_TYPE_V3 = ("TRUCK_ONLY", "CHASSIS_ONLY", "EMPTY_LOADED", "FULL_LOADED")
LEG_RATE_SOURCE = ("QUOTE_FIXED", "TARIFF_CALC", "TARIFF_FLAT", "MANUAL", "NONE")
DISTANCE_PROVIDER = ("OSRM", "GOOGLE", "MANUAL", "CACHED")
CHARGE_CATEGORY = (
    "BASE", "WAITING", "EXTRA_STOP", "DRY_RUN",
    "PENALTY", "SURCHARGE", "ADJUSTMENT", "OTHER",
)


def upgrade() -> None:
    # ════════════════════════════════════════════════════════════════
    # 1) container_stop  (v3 Stop 시퀀스)
    # ════════════════════════════════════════════════════════════════
    op.create_table(
        "container_stop",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        sa.Column("container_id", sa.Integer(), sa.ForeignKey("container.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("role", sa.Enum(*STOP_ROLE, name="stop_role"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("location.id", ondelete="SET NULL"), nullable=True),

        sa.Column("planned_arrival",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_arrival",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_departure",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),

        sa.UniqueConstraint("team_id", "id", name="uq_container_stop_team_id_id"),
        sa.UniqueConstraint("container_id", "sequence_no", name="uq_container_stop_container_seq"),
    )
    op.create_index("ix_container_stop_team_container",  "container_stop", ["team_id", "container_id", "sequence_no"])
    op.create_index("ix_container_stop_team_role",       "container_stop", ["team_id", "role"])
    op.create_index("ix_container_stop_team_location",   "container_stop", ["team_id", "location_id"])
    op.create_index("ix_container_stop_team_active_id",  "container_stop", ["team_id", "is_active", "id"])

    # ════════════════════════════════════════════════════════════════
    # 2) leg_driver_segment
    # ════════════════════════════════════════════════════════════════
    op.create_table(
        "leg_driver_segment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        sa.Column("leg_id", sa.Integer(), sa.ForeignKey("leg.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), sa.ForeignKey("driver.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("truck_id",  sa.Integer(), sa.ForeignKey("truck.id",  ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("handover_reason", sa.Enum(*HANDOVER_REASON, name="handover_reason"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),

        sa.UniqueConstraint("team_id", "id", name="uq_leg_driver_segment_team_id_id"),
        sa.UniqueConstraint("leg_id", "sequence_no", name="uq_leg_driver_segment_leg_seq"),
    )
    op.create_index("ix_leg_driver_segment_team_leg",       "leg_driver_segment", ["team_id", "leg_id", "sequence_no"])
    op.create_index("ix_leg_driver_segment_team_driver",    "leg_driver_segment", ["team_id", "driver_id"])
    op.create_index("ix_leg_driver_segment_team_active_id", "leg_driver_segment", ["team_id", "is_active", "id"])

    # ════════════════════════════════════════════════════════════════
    # 3) rate_quote
    # ════════════════════════════════════════════════════════════════
    op.create_table(
        "rate_quote",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("origin_location_id",      sa.Integer(), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=True),
        sa.Column("destination_location_id", sa.Integer(), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=True),
        sa.Column("container_size", sa.Enum("20GP","40GP","40HC","40OT","45HC","20RF","40RF", name="container_size", native_enum=True, create_type=False), nullable=True),
        sa.Column("move_type",      sa.Enum(*MOVE_TYPE_V3, name="move_type_v3"), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id", ondelete="CASCADE"), nullable=True),

        sa.Column("fixed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to",   sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),

        sa.UniqueConstraint("team_id", "id", name="uq_rate_quote_team_id_id"),
    )
    op.create_index("ix_rate_quote_team_origin",       "rate_quote", ["team_id", "origin_location_id"])
    op.create_index("ix_rate_quote_team_destination",  "rate_quote", ["team_id", "destination_location_id"])
    op.create_index("ix_rate_quote_team_customer",     "rate_quote", ["team_id", "customer_id"])
    op.create_index("ix_rate_quote_team_priority",     "rate_quote", ["team_id", "priority"])
    op.create_index("ix_rate_quote_team_effective",    "rate_quote", ["team_id", "effective_from"])
    op.create_index("ix_rate_quote_team_active_id",    "rate_quote", ["team_id", "is_active", "id"])

    # ════════════════════════════════════════════════════════════════
    # 4) rate_tariff
    # ════════════════════════════════════════════════════════════════
    op.create_table(
        "rate_tariff",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("move_type",      sa.Enum(*MOVE_TYPE_V3, name="move_type_v3", native_enum=True, create_type=False), nullable=True),
        sa.Column("container_size", sa.Enum("20GP","40GP","40HC","40OT","45HC","20RF","40RF", name="container_size", native_enum=True, create_type=False), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customer.id", ondelete="CASCADE"), nullable=True),

        sa.Column("per_value", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("per_min",   sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("flat_base", sa.Numeric(14, 2), nullable=False, server_default="0"),

        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to",   sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),

        sa.UniqueConstraint("team_id", "id", name="uq_rate_tariff_team_id_id"),
    )
    op.create_index("ix_rate_tariff_team_move",      "rate_tariff", ["team_id", "move_type"])
    op.create_index("ix_rate_tariff_team_size",      "rate_tariff", ["team_id", "container_size"])
    op.create_index("ix_rate_tariff_team_customer",  "rate_tariff", ["team_id", "customer_id"])
    op.create_index("ix_rate_tariff_team_priority",  "rate_tariff", ["team_id", "priority"])
    op.create_index("ix_rate_tariff_team_effective", "rate_tariff", ["team_id", "effective_from"])
    op.create_index("ix_rate_tariff_team_active_id", "rate_tariff", ["team_id", "is_active", "id"])

    # ════════════════════════════════════════════════════════════════
    # 5) leg_rate (snapshot freeze)
    # ════════════════════════════════════════════════════════════════
    op.create_table(
        "leg_rate",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        sa.Column("leg_id",         sa.Integer(), sa.ForeignKey("leg.id",         ondelete="CASCADE"),  nullable=False),
        sa.Column("rate_quote_id",  sa.Integer(), sa.ForeignKey("rate_quote.id",  ondelete="SET NULL"), nullable=True),
        sa.Column("rate_tariff_id", sa.Integer(), sa.ForeignKey("rate_tariff.id", ondelete="SET NULL"), nullable=True),

        sa.Column("snapshot_distance_value", sa.Numeric(14, 4), nullable=True),
        sa.Column("snapshot_duration_min",   sa.Numeric(14, 4), nullable=True),
        sa.Column("snapshot_per_value",      sa.Numeric(14, 4), nullable=True),
        sa.Column("snapshot_per_min",        sa.Numeric(14, 4), nullable=True),
        sa.Column("snapshot_flat_base",      sa.Numeric(14, 2), nullable=True),
        sa.Column("snapshot_quote_fixed",    sa.Numeric(14, 2), nullable=True),

        sa.Column("base_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("source", sa.Enum(*LEG_RATE_SOURCE, name="leg_rate_source"), nullable=False, server_default="NONE"),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("payee_driver_id", sa.Integer(), sa.ForeignKey("driver.id", ondelete="SET NULL"), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),

        sa.UniqueConstraint("team_id", "id", name="uq_leg_rate_team_id_id"),
        sa.UniqueConstraint("leg_id",          name="uq_leg_rate_leg"),
    )
    op.create_index("ix_leg_rate_team_leg",       "leg_rate", ["team_id", "leg_id"])
    op.create_index("ix_leg_rate_team_quote",     "leg_rate", ["team_id", "rate_quote_id"])
    op.create_index("ix_leg_rate_team_tariff",    "leg_rate", ["team_id", "rate_tariff_id"])
    op.create_index("ix_leg_rate_team_payee",     "leg_rate", ["team_id", "payee_driver_id"])
    op.create_index("ix_leg_rate_team_active_id", "leg_rate", ["team_id", "is_active", "id"])

    # ════════════════════════════════════════════════════════════════
    # 6) distance_matrix
    # ════════════════════════════════════════════════════════════════
    op.create_table(
        "distance_matrix",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        sa.Column("origin_location_id",      sa.Integer(), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination_location_id", sa.Integer(), sa.ForeignKey("location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("distance_value", sa.Numeric(14, 4), nullable=False),
        sa.Column("duration_min",   sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("source", sa.Enum(*DISTANCE_PROVIDER, name="distance_provider"), nullable=False, server_default="MANUAL"),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),

        sa.UniqueConstraint("team_id", "id", name="uq_distance_matrix_team_id_id"),
        sa.UniqueConstraint("team_id", "origin_location_id", "destination_location_id", name="uq_distance_matrix_pair"),
    )
    op.create_index("ix_distance_matrix_team_origin",     "distance_matrix", ["team_id", "origin_location_id"])
    op.create_index("ix_distance_matrix_team_dest",       "distance_matrix", ["team_id", "destination_location_id"])
    op.create_index("ix_distance_matrix_team_active_id",  "distance_matrix", ["team_id", "is_active", "id"])

    # ════════════════════════════════════════════════════════════════
    # 7) leg_charge: snapshot_unit_amount 추가
    # ════════════════════════════════════════════════════════════════
    op.add_column("leg_charge", sa.Column("snapshot_unit_amount", sa.Numeric(14, 2), nullable=True))

    # ════════════════════════════════════════════════════════════════
    # 8) charge_code: unit_label / category / signed / payee_default / payer_default
    # ════════════════════════════════════════════════════════════════
    op.add_column("charge_code", sa.Column("unit_label",     sa.String(32),  nullable=True))
    op.add_column("charge_code", sa.Column("category",       sa.Enum(*CHARGE_CATEGORY, name="charge_category"), nullable=True))
    op.add_column("charge_code", sa.Column("signed",         sa.Boolean(),   nullable=False, server_default=sa.text("0")))
    op.add_column("charge_code", sa.Column("payee_default",  sa.Enum("CUSTOMER","CARRIER","DRIVER","COMPANY","POOL", name="party_kind", native_enum=True, create_type=False), nullable=True))
    op.add_column("charge_code", sa.Column("payer_default",  sa.Enum("CUSTOMER","CARRIER","DRIVER","COMPANY","POOL", name="party_kind", native_enum=True, create_type=False), nullable=True))

    # ════════════════════════════════════════════════════════════════
    # 9) leg: from_stop_id / to_stop_id / move_type_v3
    # ════════════════════════════════════════════════════════════════
    op.add_column("leg", sa.Column("from_stop_id", sa.Integer(), sa.ForeignKey("container_stop.id", ondelete="SET NULL"), nullable=True))
    op.add_column("leg", sa.Column("to_stop_id",   sa.Integer(), sa.ForeignKey("container_stop.id", ondelete="SET NULL"), nullable=True))
    op.add_column("leg", sa.Column("move_type_v3", sa.Enum(*MOVE_TYPE_V3, name="move_type_v3", native_enum=True, create_type=False), nullable=True))

    # 기존 데이터 백필: move_type → move_type_v3
    op.execute("UPDATE leg SET move_type_v3='FULL_LOADED' WHERE move_type='LOADED'")
    op.execute("UPDATE leg SET move_type_v3='EMPTY_LOADED' WHERE move_type='EMPTY'")
    op.execute("UPDATE leg SET move_type_v3='TRUCK_ONLY'   WHERE move_type='BOBTAIL'")

    # ════════════════════════════════════════════════════════════════
    # 10) container: work_state 8단계
    # ════════════════════════════════════════════════════════════════
    op.add_column("container", sa.Column(
        "work_state", sa.Enum(*CONTAINER_STATE, name="container_state"),
        nullable=False, server_default="DRAFT",
    ))
    # 기존 status 매핑: PLANNING→DRAFT, DISPATCHED→PLANNED,
    #   YARD_STAGED/FINAL_DELIVERY/EMPTY_STAGED→IN_TRANSIT, COMPLETED→COMPLETED
    op.execute("UPDATE container SET work_state='DRAFT'      WHERE status='PLANNING'")
    op.execute("UPDATE container SET work_state='PLANNED'    WHERE status='DISPATCHED'")
    op.execute("UPDATE container SET work_state='IN_TRANSIT' WHERE status IN ('YARD_STAGED','FINAL_DELIVERY','EMPTY_STAGED')")
    op.execute("UPDATE container SET work_state='COMPLETED'  WHERE status='COMPLETED'")

    # ════════════════════════════════════════════════════════════════
    # 11) team: distance_unit_label / currency_label / currency_symbol /
    #     distance_provider / distance_provider_config
    # ════════════════════════════════════════════════════════════════
    op.add_column("teams", sa.Column("distance_unit_label",      sa.String(16),   nullable=True, server_default="km"))
    op.add_column("teams", sa.Column("currency_label",           sa.String(16),   nullable=True))
    op.add_column("teams", sa.Column("currency_symbol",          sa.String(8),    nullable=True))
    op.add_column("teams", sa.Column("distance_provider",        sa.String(32),   nullable=True, server_default="MANUAL"))
    op.add_column("teams", sa.Column("distance_provider_config", sa.String(2000), nullable=True))


def downgrade() -> None:
    # ── 11) team
    op.drop_column("teams", "distance_provider_config")
    op.drop_column("teams", "distance_provider")
    op.drop_column("teams", "currency_symbol")
    op.drop_column("teams", "currency_label")
    op.drop_column("teams", "distance_unit_label")

    # ── 10) container
    op.drop_column("container", "work_state")
    sa.Enum(name="container_state").drop(op.get_bind(), checkfirst=True)

    # ── 9) leg
    op.drop_column("leg", "move_type_v3")
    op.drop_column("leg", "to_stop_id")
    op.drop_column("leg", "from_stop_id")

    # ── 8) charge_code
    op.drop_column("charge_code", "payer_default")
    op.drop_column("charge_code", "payee_default")
    op.drop_column("charge_code", "signed")
    op.drop_column("charge_code", "category")
    op.drop_column("charge_code", "unit_label")
    sa.Enum(name="charge_category").drop(op.get_bind(), checkfirst=True)

    # ── 7) leg_charge
    op.drop_column("leg_charge", "snapshot_unit_amount")

    # ── 6) distance_matrix
    op.drop_index("ix_distance_matrix_team_active_id", table_name="distance_matrix")
    op.drop_index("ix_distance_matrix_team_dest",      table_name="distance_matrix")
    op.drop_index("ix_distance_matrix_team_origin",    table_name="distance_matrix")
    op.drop_table("distance_matrix")
    sa.Enum(name="distance_provider").drop(op.get_bind(), checkfirst=True)

    # ── 5) leg_rate
    op.drop_index("ix_leg_rate_team_active_id", table_name="leg_rate")
    op.drop_index("ix_leg_rate_team_payee",     table_name="leg_rate")
    op.drop_index("ix_leg_rate_team_tariff",    table_name="leg_rate")
    op.drop_index("ix_leg_rate_team_quote",     table_name="leg_rate")
    op.drop_index("ix_leg_rate_team_leg",       table_name="leg_rate")
    op.drop_table("leg_rate")
    sa.Enum(name="leg_rate_source").drop(op.get_bind(), checkfirst=True)

    # ── 4) rate_tariff
    op.drop_index("ix_rate_tariff_team_active_id", table_name="rate_tariff")
    op.drop_index("ix_rate_tariff_team_effective", table_name="rate_tariff")
    op.drop_index("ix_rate_tariff_team_priority",  table_name="rate_tariff")
    op.drop_index("ix_rate_tariff_team_customer",  table_name="rate_tariff")
    op.drop_index("ix_rate_tariff_team_size",      table_name="rate_tariff")
    op.drop_index("ix_rate_tariff_team_move",      table_name="rate_tariff")
    op.drop_table("rate_tariff")

    # ── 3) rate_quote
    op.drop_index("ix_rate_quote_team_active_id", table_name="rate_quote")
    op.drop_index("ix_rate_quote_team_effective", table_name="rate_quote")
    op.drop_index("ix_rate_quote_team_priority",  table_name="rate_quote")
    op.drop_index("ix_rate_quote_team_customer",  table_name="rate_quote")
    op.drop_index("ix_rate_quote_team_destination","rate_quote")
    op.drop_index("ix_rate_quote_team_origin",    table_name="rate_quote")
    op.drop_table("rate_quote")
    sa.Enum(name="move_type_v3").drop(op.get_bind(), checkfirst=True)

    # ── 2) leg_driver_segment
    op.drop_index("ix_leg_driver_segment_team_active_id", table_name="leg_driver_segment")
    op.drop_index("ix_leg_driver_segment_team_driver",    table_name="leg_driver_segment")
    op.drop_index("ix_leg_driver_segment_team_leg",       table_name="leg_driver_segment")
    op.drop_table("leg_driver_segment")
    sa.Enum(name="handover_reason").drop(op.get_bind(), checkfirst=True)

    # ── 1) container_stop
    op.drop_index("ix_container_stop_team_active_id", table_name="container_stop")
    op.drop_index("ix_container_stop_team_location",  table_name="container_stop")
    op.drop_index("ix_container_stop_team_role",      table_name="container_stop")
    op.drop_index("ix_container_stop_team_container", table_name="container_stop")
    op.drop_table("container_stop")
    sa.Enum(name="stop_role").drop(op.get_bind(), checkfirst=True)
