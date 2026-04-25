"""Notification 스키마."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.schema import BaseSchema
from app.models.enums import NotificationChannel, NotificationStatus


class NotificationCreateRequest(BaseSchema):
    user_id: str | None = None
    channel: NotificationChannel = NotificationChannel.PUSH
    event_type: str = Field(..., max_length=64)
    title: str = Field(..., max_length=255)
    body: str | None = None
    payload: dict | None = None


class NotificationResponse(BaseSchema):
    id: str
    tenant_id: str
    user_id: str | None
    channel: NotificationChannel
    status: NotificationStatus
    event_type: str
    title: str
    body: str | None
    payload: dict | None
    is_read: bool
    read_at: datetime | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime
