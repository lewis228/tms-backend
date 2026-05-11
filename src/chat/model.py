# src/chat/model.py
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Text, Integer, Boolean, ForeignKey, DateTime,
    Index, UniqueConstraint, Enum as SAEnum,
)

from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from chat.const.sender import ChatSenderType


class ChatMessageModel(Base, TeamScopedMixin):
    """관제 ↔ 기사 1:1 채팅 메시지 (driver app).

    한 driver 와 그 팀의 dispatcher(들) 사이 메시지. driver_user_id 가 conversation key.
    데모용 — 실제 운영은 conversation 테이블 분리 + 다자 채팅 확장.
    """
    __tablename__ = "chat_message"

    # 어느 driver 와의 conversation 인지 (user 글로벌 FK)
    driver_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False,
    )

    sender_type: Mapped[ChatSenderType] = mapped_column(
        SAEnum(ChatSenderType, name="chat_sender_type"), nullable=False,
    )
    # 발신자 user_id (DISPATCHER 면 그 디스패처. SYSTEM 면 NULL)
    sender_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 읽음 표시 (단순 — 읽은 시각만 보관. unread = read_at IS NULL)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_chat_message_team_id_id"),
        # driver 별 conversation 페이지네이션 빠른 조회
        Index("ix_chat_team_driver_created", "team_id", "driver_user_id", "created_at"),
        Index("ix_chat_team_active_id",      "team_id", "is_active", "id"),
        Index("ix_chat_team_updated_at",     "team_id", "updated_at"),
    )
