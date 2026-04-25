from __future__ import annotations
from typing import Optional
from datetime import datetime
from common.schemas.base import ResponseSchema


class TagResponseSchema(ResponseSchema):
    id: int
    team_id: int
    name: str
    color: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
