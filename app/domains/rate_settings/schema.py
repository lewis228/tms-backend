"""RateSetting 스키마."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, model_validator

from app.core.schema import BaseSchema
from app.models.enums import RateType


class RateSettingCreateRequest(BaseSchema):
    name: str = Field(..., min_length=1, max_length=128)
    rate_type: RateType
    flat_amount: Decimal | None = None
    rate_percent: Decimal | None = None
    rate_per_mile: Decimal | None = None
    effective_date: date
    description: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_amount(self):
        mapping = {
            RateType.FLAT_RATE: self.flat_amount,
            RateType.PERCENTAGE: self.rate_percent,
            RateType.PER_MILE: self.rate_per_mile,
        }
        if mapping[self.rate_type] is None:
            raise ValueError(f"Field for rate_type {self.rate_type.value} is required")
        return self


class RateSettingUpdateRequest(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    flat_amount: Decimal | None = None
    rate_percent: Decimal | None = None
    rate_per_mile: Decimal | None = None
    effective_date: date | None = None
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=500)


class RateSettingResponse(BaseSchema):
    id: str
    tenant_id: str
    name: str
    rate_type: RateType
    flat_amount: Decimal | None
    rate_percent: Decimal | None
    rate_per_mile: Decimal | None
    effective_date: date
    is_active: bool
    description: str | None
    created_at: datetime
    updated_at: datetime
