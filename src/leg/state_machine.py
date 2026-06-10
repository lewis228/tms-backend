# src/leg/state_machine.py
"""Leg 상태머신 — 전이 그래프의 단일 진실.

PENDING → ASSIGNED → IN_TRANSIT → COMPLETED / FAILED
  - PENDING→ASSIGNED : 드라이버 배차
  - ASSIGNED→PENDING : 배차 취소
  - PENDING→IN_TRANSIT: 즉시 출발(드라이버앱 체크포인트)
  - IN_TRANSIT→FAILED: failure_reason 필수
  - FAILED→PENDING : 재배차

DRY_RUN(빠꾸) 은 transition() 으로 가는 전이가 아니다 — reissue_dry_run() 이
원본 leg 를 DRY_RUN 으로 직접 종료하며 새 leg 를 발급한다. 따라서 종료 상태로만 표기.

leg/service.transition() 과 배차 액션·D/O 파생엔진 모두 이 모듈을 참조한다.
"""
from __future__ import annotations

from common.exceptions.base import AppException
from leg.const.status import LegStatus


_ALLOWED: dict[LegStatus, set[LegStatus]] = {
    LegStatus.PENDING:    {LegStatus.ASSIGNED, LegStatus.IN_TRANSIT},
    LegStatus.ASSIGNED:   {LegStatus.IN_TRANSIT, LegStatus.PENDING},
    LegStatus.IN_TRANSIT: {LegStatus.COMPLETED, LegStatus.FAILED},
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
