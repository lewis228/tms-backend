# src/leg/state_machine.py
"""Leg 상태머신 (컨플루언스 재설계) — 전이 그래프의 단일 진실.

PENDING → ASSIGNED → IN_TRANSIT → COMPLETED / FAILED
  - PENDING→ASSIGNED : 드라이버 배차
  - ASSIGNED→PENDING : 배차 취소
  - PENDING→IN_TRANSIT: (레거시/즉시출발 허용 — 드라이버앱 체크포인트 호환)
  - IN_TRANSIT→FAILED: failure_reason 필수
  - FAILED→PENDING : 재배차

기존 leg/service.transition() 의 인라인 그래프와 동일하게 유지한다.
배차 액션·D/O 파생엔진 등 신규 코드는 이 모듈을 참조.
"""
from __future__ import annotations

from common.exceptions.base import AppException
from leg.const.status import LegStatus


# DRY_RUN(빠꾸) = 현장 도착했으나 작업 불가 → 종료 상태. reissue 로 새 leg 발급.
_ALLOWED: dict[LegStatus, set[LegStatus]] = {
    LegStatus.PENDING:    {LegStatus.ASSIGNED, LegStatus.IN_TRANSIT},
    LegStatus.ASSIGNED:   {LegStatus.IN_TRANSIT, LegStatus.PENDING, LegStatus.DRY_RUN},
    LegStatus.IN_TRANSIT: {LegStatus.COMPLETED, LegStatus.FAILED, LegStatus.DRY_RUN},
    LegStatus.COMPLETED:  set(),
    LegStatus.FAILED:     {LegStatus.PENDING},
    LegStatus.DRY_RUN:    set(),
}


class InvalidLegTransition(AppException):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            code="ERR_INVALID_LEG_TRANSITION",
            message=message, status_code=422, detail=details,
        )


def allowed_targets(current: LegStatus) -> set[LegStatus]:
    return _ALLOWED.get(current, set())


def assert_can_transition(current: LegStatus, target: LegStatus, *, force: bool = False) -> None:
    if force:
        return
    if target not in _ALLOWED.get(current, set()):
        raise InvalidLegTransition(
            f"Cannot transition leg {current.value} → {target.value}",
            details={
                "from": current.value, "to": target.value,
                "allowed": [s.value for s in _ALLOWED.get(current, set())],
            },
        )
