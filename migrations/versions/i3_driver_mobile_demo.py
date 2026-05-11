"""I-3 Driver mobile 데모 — chat / leg accept / driver duty.

추가 컬럼:
  - driver.duty_status (Enum), driver.duty_changed_at (DateTime tz)
  - leg.offered_at, leg.accepted_at, leg.rejected_at (DateTime tz)
  - leg.rejection_reason (String 500)
  - leg.ix_leg_team_driver_offered 인덱스

신규 테이블:
  - chat_message (driver ↔ dispatcher 1:1 채팅)

Revision ID: i3drivermob00011
Revises: i2v3audit00010
Create Date: 2026-05-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i3drivermob00011"
down_revision: Union[str, None] = "i2v3audit00010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum 값들 — model 의 StrEnum 과 일치
DUTY_STATUS_VALUES = ("OFF_DUTY", "ON_DUTY", "IN_BREAK")
CHAT_SENDER_VALUES = ("DRIVER", "DISPATCHER", "SYSTEM")


def upgrade() -> None:
    # ── 1) driver.duty_status / duty_changed_at ───────────
    duty_enum = sa.Enum(*DUTY_STATUS_VALUES, name="duty_status")
    duty_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "driver",
        sa.Column(
            "duty_status",
            duty_enum,
            nullable=False,
            server_default="OFF_DUTY",
        ),
    )
    op.add_column(
        "driver",
        sa.Column("duty_changed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── 2) leg.offered_at / accepted_at / rejected_at / rejection_reason ─
    op.add_column("leg", sa.Column("offered_at",       sa.DateTime(timezone=True), nullable=True))
    op.add_column("leg", sa.Column("accepted_at",      sa.DateTime(timezone=True), nullable=True))
    op.add_column("leg", sa.Column("rejected_at",      sa.DateTime(timezone=True), nullable=True))
    op.add_column("leg", sa.Column("rejection_reason", sa.String(500),              nullable=True))
    op.create_index(
        "ix_leg_team_driver_offered",
        "leg",
        ["team_id", "driver_id", "offered_at", "accepted_at"],
        unique=False,
    )

    # ── 3) chat_message 테이블 ───────────────────────────
    chat_sender_enum = sa.Enum(*CHAT_SENDER_VALUES, name="chat_sender_type")
    chat_sender_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "chat_message",
        # Base 공통 컬럼
        sa.Column("id",        sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("is_active", sa.Boolean(),  nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=True),
        # team scoped
        sa.Column("team_id",   sa.Integer(),  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        # chat 도메인
        sa.Column("driver_user_id",   sa.Integer(),         sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_type",      chat_sender_enum,     nullable=False),
        sa.Column("sender_user_id",   sa.Integer(),         sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content",          sa.Text(),            nullable=False),
        sa.Column("read_at",          sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("team_id", "id", name="uq_chat_message_team_id_id"),
    )
    op.create_index("ix_chat_message_team_id",            "chat_message", ["team_id"])
    op.create_index("ix_chat_team_driver_created",        "chat_message", ["team_id", "driver_user_id", "created_at"])
    op.create_index("ix_chat_team_active_id",             "chat_message", ["team_id", "is_active", "id"])
    op.create_index("ix_chat_team_updated_at",            "chat_message", ["team_id", "updated_at"])


def downgrade() -> None:
    # chat_message
    op.drop_index("ix_chat_team_updated_at",      table_name="chat_message")
    op.drop_index("ix_chat_team_active_id",       table_name="chat_message")
    op.drop_index("ix_chat_team_driver_created",  table_name="chat_message")
    op.drop_index("ix_chat_message_team_id",      table_name="chat_message")
    op.drop_table("chat_message")
    sa.Enum(name="chat_sender_type").drop(op.get_bind(), checkfirst=True)

    # leg
    op.drop_index("ix_leg_team_driver_offered", table_name="leg")
    op.drop_column("leg", "rejection_reason")
    op.drop_column("leg", "rejected_at")
    op.drop_column("leg", "accepted_at")
    op.drop_column("leg", "offered_at")

    # driver
    op.drop_column("driver", "duty_changed_at")
    op.drop_column("driver", "duty_status")
    sa.Enum(name="duty_status").drop(op.get_bind(), checkfirst=True)
