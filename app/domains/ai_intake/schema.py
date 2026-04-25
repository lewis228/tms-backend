"""AI Intake 스키마 — D/O 마스터 추출 결과."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.core.schema import BaseSchema
from app.models.enums import ContainerSize, ShipmentDirection


class IntakeExtractRequest(BaseSchema):
    """업로드된 파일 (file_id) 또는 base64 데이터를 추출.

    file_id 는 files 도메인에 미리 업로드된 파일을 가리킴.
    """

    file_id: str | None = None
    media_type: str = Field(default="application/pdf")
    base64_data: str | None = None
    hint_direction: ShipmentDirection | None = None


class IntakeField(BaseSchema):
    value: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class IntakeExtractResponse(BaseSchema):
    direction: ShipmentDirection | None = None
    bl_number: IntakeField | None = None
    booking_number: IntakeField | None = None
    container_number: IntakeField | None = None
    container_size: ContainerSize | None = None
    chassis_number: IntakeField | None = None
    customer_name: IntakeField | None = None
    terminal_name: IntakeField | None = None
    vessel_name: IntakeField | None = None
    eta: datetime | None = None
    pickup_appointment: datetime | None = None
    delivery_appointment: datetime | None = None
    demurrage_lfd: date | None = None
    overall_confidence: float = 0.0
    raw_text: str | None = None
    model: str
