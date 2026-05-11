# src/chat/const/sender.py
from __future__ import annotations
from enum import StrEnum


class ChatSenderType(StrEnum):
    """채팅 메시지 발신자 타입.

    DRIVER     — 기사 (모바일 앱 사용자)
    DISPATCHER — 관제사 (web 또는 시스템 자동 응답)
    SYSTEM     — 시스템 알림 (배차 안내 등)
    """
    DRIVER     = "DRIVER"
    DISPATCHER = "DISPATCHER"
    SYSTEM     = "SYSTEM"
