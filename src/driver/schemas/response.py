# src/driver/schemas/response.py
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Literal, List, Optional
from common.schemas.base import ResponseSchema
from driver.const.status import EmploymentKind, PaymentTermsKind


class DriverResponseSchema(ResponseSchema):
    id: int
    user_id: int
    email: str | None = None
    name: str | None = None
    phone: str | None = None
    license_number: str | None = None
    license_state: str | None = None
    note: str | None = None
    is_active: bool
    # H-5
    employment_kind: EmploymentKind
    carrier_id: int | None = None
    payment_terms_kind: PaymentTermsKind | None = None
    payment_terms_value: Decimal | None = None
    default_truck_id: int | None = None
    default_chassis_id: int | None = None
    license_expires_at: date | None = None
    medical_cert_expires_at: date | None = None
    twic_expires_at: date | None = None
    hire_date: date | None = None


class DriverDeleteResponseSchema(ResponseSchema):
    id: int
    object: Literal["driver"] = "driver"
    deleted: bool = True
    soft_deleted: bool = False


class BulkResultItem(ResponseSchema):
    id: int
    success: bool
    data: Optional[DriverResponseSchema] = None
    error: Optional[str] = None


class BulkDeleteResultItem(ResponseSchema):
    id: int
    success: bool
    soft_deleted: bool = False
    error: Optional[str] = None


class BulkSummary(ResponseSchema):
    total: int
    succeeded: int
    failed: int


class DriverBulkCreateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class DriverBulkUpdateResponseSchema(ResponseSchema):
    results: List[BulkResultItem]
    summary: BulkSummary


class DriverBulkDeleteResponseSchema(ResponseSchema):
    results: List[BulkDeleteResultItem]
    summary: BulkSummary
