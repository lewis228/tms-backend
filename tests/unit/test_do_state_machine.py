# tests/unit/test_do_state_machine.py
"""D/O 상태 머신 + dispatch 파생 unit 테스트 (DB 없음).

재설계 후:
  - state_machine.assert_can_transition 은 단순 전이 매트릭스(_ALLOWED) + force 점프만 검증.
    세부 게이트(위치 종류/일정/플래그)는 제거됨 → 파생 엔진(state_derive)이 leg 기준으로 관리.
  - state_derive.compute_dispatch_status 가 DISPATCHING/DISPATCHED/PLANNING 자동 파생 규칙의 핵심.

state machine 은 attr 접근만 함 → SQLAlchemy 모델 대신 SimpleNamespace shim.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from delivery_order.const.status import DeliveryStatus
from delivery_order.state_machine import (
    InvalidStateTransitionError,
    TransitionContext,
    assert_can_transition,
)
from delivery_order.state_derive import compute_dispatch_status
from leg.const.status import LegStatus


# ── shim helpers ───────────────────────────────────────────────────
def make_do(status=DeliveryStatus.PLANNING, **kw) -> SimpleNamespace:
    return SimpleNamespace(status=status, **kw)


def make_leg(**kw) -> SimpleNamespace:
    defaults = dict(
        status=LegStatus.PENDING,
        driver_id=None,
        is_active=True,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def ctx(do, legs=None) -> TransitionContext:
    return TransitionContext(do=do, legs=legs or [])


# ── 1) 전이 매트릭스 ────────────────────────────────────────────────
class TestTransitionGraph:
    def test_planning_to_dispatching_ok(self):
        assert_can_transition(ctx(make_do(DeliveryStatus.PLANNING)), DeliveryStatus.DISPATCHING)

    def test_planning_to_dispatched_ok(self):
        assert_can_transition(ctx(make_do(DeliveryStatus.PLANNING)), DeliveryStatus.DISPATCHED)

    def test_planning_cannot_jump_to_final_delivery(self):
        with pytest.raises(InvalidStateTransitionError):
            assert_can_transition(ctx(make_do(DeliveryStatus.PLANNING)), DeliveryStatus.FINAL_DELIVERY)

    def test_dispatched_can_regress_to_dispatching(self):
        # 새 미배차 leg 생기면 DISPATCHING 회귀 — 매트릭스가 허용해야 함
        assert_can_transition(ctx(make_do(DeliveryStatus.DISPATCHED)), DeliveryStatus.DISPATCHING)

    def test_yard_staged_only_to_allowed(self):
        with pytest.raises(InvalidStateTransitionError):
            assert_can_transition(ctx(make_do(DeliveryStatus.YARD_STAGED)), DeliveryStatus.EMPTY_STAGED)

    def test_completed_can_correct_back_to_empty_staged(self):
        assert_can_transition(ctx(make_do(DeliveryStatus.COMPLETED)), DeliveryStatus.EMPTY_STAGED)

    def test_completed_cannot_go_to_planning(self):
        with pytest.raises(InvalidStateTransitionError):
            assert_can_transition(ctx(make_do(DeliveryStatus.COMPLETED)), DeliveryStatus.PLANNING)


# ── 2) force 점프 ──────────────────────────────────────────────────
class TestForceJump:
    def test_force_skips_matrix(self):
        # 정상적으론 불가한 전이도 force=True 면 통과 (관리자 점프)
        assert_can_transition(
            ctx(make_do(DeliveryStatus.PLANNING)), DeliveryStatus.COMPLETED, force=True,
        )


# ── 3) dispatch 파생 규칙 (핵심 비즈니스 룰) ─────────────────────────
class TestComputeDispatchStatus:
    def test_no_legs_is_planning(self):
        assert compute_dispatch_status([]) == DeliveryStatus.PLANNING

    def test_only_inactive_legs_is_planning(self):
        assert compute_dispatch_status([make_leg(is_active=False)]) == DeliveryStatus.PLANNING

    def test_unassigned_leg_is_dispatching(self):
        # 활성 leg 1개 + 미배차 → DISPATCHING
        legs = [make_leg(driver_id=None, status=LegStatus.PENDING)]
        assert compute_dispatch_status(legs) == DeliveryStatus.DISPATCHING

    def test_all_assigned_is_dispatched(self):
        # 활성 leg 모두 배차 완료 → DISPATCHED
        legs = [
            make_leg(driver_id=1, status=LegStatus.ASSIGNED),
            make_leg(driver_id=2, status=LegStatus.ASSIGNED),
        ]
        assert compute_dispatch_status(legs) == DeliveryStatus.DISPATCHED

    def test_one_unassigned_among_many_is_dispatching(self):
        # 하나라도 미배차면 DISPATCHING
        legs = [
            make_leg(driver_id=1, status=LegStatus.ASSIGNED),
            make_leg(driver_id=None, status=LegStatus.PENDING),
        ]
        assert compute_dispatch_status(legs) == DeliveryStatus.DISPATCHING

    def test_in_transit_unassigned_does_not_force_dispatching(self):
        # 미배차여도 status 가 배차단계(PENDING/ASSIGNED)가 아니면 무시 → DISPATCHED
        legs = [make_leg(driver_id=None, status=LegStatus.IN_TRANSIT)]
        assert compute_dispatch_status(legs) == DeliveryStatus.DISPATCHED
