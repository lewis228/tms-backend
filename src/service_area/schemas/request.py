# src/service_area/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal
from pydantic import Field, model_validator

from common.schemas.base import RequestSchema
from common.pagination.schemas.pagination_request import BasePaginationSchema
from service_area.const.status import ServiceAreaKind


class ServiceAreaCreateRequest(RequestSchema):
    """영업권역 선언 1건 추가.

    - STATE: value 생략 가능 (state 로 자동 보정)
    - ZIP3: value 는 3자리 숫자 prefix (예: "902")
    """
    kind: ServiceAreaKind
    state: str = Field(min_length=2, max_length=8)
    value: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _normalize(self):
        self.state = self.state.strip().upper()
        if self.kind == ServiceAreaKind.STATE:
            self.value = self.state
        else:
            v = (self.value or "").strip()
            if not v:
                raise ValueError(f"{self.kind.value} 선언에는 value 가 필요합니다.")
            if self.kind == ServiceAreaKind.ZIP3:
                if not (v.isdigit() and len(v) == 3):
                    raise ValueError("ZIP3 prefix 는 3자리 숫자여야 합니다 (예: 902).")
            self.value = v
        return self


class PaginateServiceAreaRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'ASC'

    include_inactive: bool = False

    where__kind__equal: Optional[ServiceAreaKind] = None
    where__state__equal: Optional[str] = None
