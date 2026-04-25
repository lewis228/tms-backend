from __future__ import annotations
from typing import Optional
from pydantic import Field
from common.schemas.base import RequestSchema


class CreateTagRequestSchema(RequestSchema):
    name: str = Field(..., min_length=1, max_length=80)
    # Accepts any hex or CSS colour — stored verbatim. Kept optional so the
    # frontend can let the server auto-assign from a palette later.
    color: Optional[str] = Field(default=None, max_length=20)


class UpdateTagRequestSchema(RequestSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    color: Optional[str] = Field(default=None, max_length=20)
