from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ListLocationsQuerySchema(BaseModel):
    """Query params for GET /locations — picker / autocomplete feeds."""

    search: Optional[str] = Field(default=None, max_length=100)
    country_code: Optional[str] = Field(default=None, max_length=2)
    kind: Optional[str] = Field(default=None, max_length=20)
    # Default picker shows only supported entries. Admin UIs can pass false.
    supported_only: bool = True
    # Paging — the UN/LOCODE set is 110K+ so always cap.
    limit: int = Field(default=50, ge=1, le=200)
