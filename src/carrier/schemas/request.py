from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class ListCarriersQuerySchema(BaseModel):
    """Query parameters for GET /carriers."""

    # When true (default), returns only is_supported=true carriers — the
    # normal case for the picker. Admin UIs can pass false to see everything.
    supported_only: bool = True
    # Free-text filter on name / scac for search-as-you-type.
    search: Optional[str] = Field(default=None, max_length=100)
    # Restrict to carriers that have a working scraper.
    scrapable_only: bool = False
