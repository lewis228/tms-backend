from __future__ import annotations
from typing import Optional
from pydantic import Field
from common.schemas.base import RequestSchema


class CreateCustomerRequestSchema(RequestSchema):
    name: str = Field(..., min_length=1, max_length=100)


class UpdateCustomerRequestSchema(RequestSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
