# src/notification/const/channel.py
from __future__ import annotations
from enum import StrEnum


class NotificationChannel(StrEnum):
    """알림 채널."""
    PUSH    = "PUSH"     # 모바일 푸시 + in-app
    EMAIL   = "EMAIL"
    SMS     = "SMS"
    WEBHOOK = "WEBHOOK"


class NotificationStatus(StrEnum):
    """발송 상태 (in-app 은 PENDING/SENT 만 의미 있음)."""
    PENDING   = "PENDING"
    SENT      = "SENT"
    FAILED    = "FAILED"
    DELIVERED = "DELIVERED"
