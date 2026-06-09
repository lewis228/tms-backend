# src/audit_log/schemas/response.py
from __future__ import annotations
from datetime import datetime
from common.schemas.base import ResponseSchema


class AuditLogResponseSchema(ResponseSchema):
    id: int
    entity_type: str
    entity_id: int
    action: str
    summary: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    created_by_user_id: int | None = None
    created_at: datetime | None = None
