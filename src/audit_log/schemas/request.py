# src/audit_log/schemas/request.py
from __future__ import annotations
from typing import Optional, Literal
from common.pagination.schemas.pagination_request import BasePaginationSchema


class PaginateAuditLogRequest(BasePaginationSchema):
    order__id: Optional[Literal['ASC', 'DESC']] = 'DESC'
    where__entity_type__equal: Optional[str] = None
    where__action__equal: Optional[str] = None
