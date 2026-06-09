# src/invoice/state_machine.py
"""Invoice 상태 전이 (재설계 2c).

DRAFT → ISSUED → PAID, 어디서든 VOID 가능(PAID 제외는 정책상 허용).
라인 편집은 DRAFT 에서만(service 가 강제).
"""
from __future__ import annotations

from common.exceptions.base import AppException
from invoice.const.status import InvoiceStatus


class InvalidInvoiceTransitionError(AppException):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            code="ERR_INVALID_INVOICE_TRANSITION",
            message=message, status_code=422, detail=details,
        )


_ALLOWED: dict[InvoiceStatus, set[InvoiceStatus]] = {
    InvoiceStatus.DRAFT:  {InvoiceStatus.ISSUED, InvoiceStatus.VOID},
    InvoiceStatus.ISSUED: {InvoiceStatus.PAID, InvoiceStatus.VOID, InvoiceStatus.DRAFT},
    InvoiceStatus.PAID:   {InvoiceStatus.VOID},
    InvoiceStatus.VOID:   set(),
}


def assert_can_transition(src: InvoiceStatus, target: InvoiceStatus) -> None:
    if target not in _ALLOWED.get(src, set()):
        raise InvalidInvoiceTransitionError(
            f"Cannot transition {src.value} → {target.value}",
            details={"from": src.value, "to": target.value,
                     "allowed": [s.value for s in _ALLOWED.get(src, set())]},
        )
