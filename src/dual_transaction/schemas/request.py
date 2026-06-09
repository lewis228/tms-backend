# src/dual_transaction/schemas/request.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal

from pydantic import Field, model_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from dual_transaction.const.status import DualTransactionStatus


class DualTransactionCreateRequest(RequestSchema):
    """반납 leg + 픽업 leg 를 한 드라이버로 묶음."""
    driver_id: int
    return_leg_id: int
    pickup_leg_id: int
    truck_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check(self):
        if self.return_leg_id == self.pickup_leg_id:
            raise ValueError("return_leg_id 와 pickup_leg_id 는 서로 달라야 합니다.")
        return self


class DualTransactionUpdateRequest(RequestSchema):
    truck_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=500)


class PaginateDualTransactionRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    include_inactive: bool = False
    where__driver_id__equal: Optional[int] = None
    where__status__equal: Optional[DualTransactionStatus] = None
