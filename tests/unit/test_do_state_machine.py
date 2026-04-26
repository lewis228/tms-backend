# tests/unit/test_do_state_machine.py
"""D/O 상태 머신 unit 테스트 (DB 없음).

state_machine 은 attr 접근만 함 → SQLAlchemy 모델 대신 SimpleNamespace shim.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from types import SimpleNamespace

import pytest

from delivery_order.const.status import DeliveryStatus, ShipmentDirection
from delivery_order.state_machine import (
    InvalidStateTransitionError,
    TransitionContext,
    assert_can_transition,
)
from leg.const.status import LegStatus
from location.const.kind import LocationKind


# ── shim helpers ───────────────────────────────────────────────────
def make_do(**kw) -> SimpleNamespace:
    defaults = dict(
        status=DeliveryStatus.PLANNING,
        direction=ShipmentDirection.IMPORT,
        bl_released=True,
        pier_pass_paid=True,
        customs_cleared=True,
        pickup_appointment=datetime(2026, 5, 1, 9, tzinfo=timezone.utc),
        delivery_appointment=datetime(2026, 5, 1, 14, tzinfo=timezone.utc),
        return_appointment=datetime(2026, 5, 2, 9, tzinfo=timezone.utc),
        detention_lfd=date(2026, 5, 3),
        empty_date=date(2026, 5, 2),
        loaded_date=None,
        return_location_id=10,
        delivery_location_id=20,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_leg(**kw) -> SimpleNamespace:
    defaults = dict(
        status=LegStatus.COMPLETED,
        driver_id=1,
        pickup_date=datetime(2026, 5, 1, 9, tzinfo=timezone.utc),
        completed_at=datetime(2026, 5, 1, 11, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 1, 8, tzinfo=timezone.utc),
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_location(kind: LocationKind) -> SimpleNamespace:
    return SimpleNamespace(kind=kind)


def ctx(do, legs=None, delivery_loc=LocationKind.CUSTOMER, return_loc=LocationKind.YARD):
    return TransitionContext(
        do=do,
        legs=legs or [],
        delivery_location=make_location(delivery_loc) if delivery_loc else None,
        return_location=make_location(return_loc) if return_loc else None,
    )


# ── 1) 기본 전이 그래프 ────────────────────────────────────────────
class TestTransitionGraph:
    def test_planning_can_only_go_to_dispatched(self):
        do = make_do(status=DeliveryStatus.PLANNING)
        with pytest.raises(InvalidStateTransitionError):
            assert_can_transition(ctx(do, [make_leg(status=LegStatus.PENDING)]),
                                  DeliveryStatus.FINAL_DELIVERY)

    def test_completed_is_terminal(self):
        do = make_do(status=DeliveryStatus.COMPLETED)
        with pytest.raises(InvalidStateTransitionError):
            assert_can_transition(ctx(do), DeliveryStatus.PLANNING)

    def test_yard_staged_only_to_final_delivery(self):
        do = make_do(status=DeliveryStatus.YARD_STAGED)
        with pytest.raises(InvalidStateTransitionError):
            assert_can_transition(ctx(do), DeliveryStatus.EMPTY_STAGED)


# ── 2) PLANNING → DISPATCHED ───────────────────────────────────────
class TestPlanningToDispatched:
    def _ctx_ok(self):
        return ctx(make_do(status=DeliveryStatus.PLANNING),
                   [make_leg(status=LegStatus.PENDING)])

    def test_happy_path(self):
        assert_can_transition(self._ctx_ok(), DeliveryStatus.DISPATCHED)

    def test_requires_first_leg(self):
        with pytest.raises(InvalidStateTransitionError, match="first leg 필수"):
            assert_can_transition(ctx(make_do(status=DeliveryStatus.PLANNING), []),
                                  DeliveryStatus.DISPATCHED)

    def test_requires_bl_released(self):
        do = make_do(status=DeliveryStatus.PLANNING, bl_released=False)
        with pytest.raises(InvalidStateTransitionError, match="bl_released"):
            assert_can_transition(ctx(do, [make_leg(status=LegStatus.PENDING)]),
                                  DeliveryStatus.DISPATCHED)

    def test_requires_pickup_appointment(self):
        do = make_do(status=DeliveryStatus.PLANNING, pickup_appointment=None)
        with pytest.raises(InvalidStateTransitionError, match="pickup_appointment"):
            assert_can_transition(ctx(do, [make_leg(status=LegStatus.PENDING)]),
                                  DeliveryStatus.DISPATCHED)

    def test_requires_first_leg_driver_id(self):
        do = make_do(status=DeliveryStatus.PLANNING)
        with pytest.raises(InvalidStateTransitionError, match="driver_id"):
            assert_can_transition(
                ctx(do, [make_leg(status=LegStatus.PENDING, driver_id=None)]),
                DeliveryStatus.DISPATCHED,
            )

    def test_requires_first_leg_pickup_date(self):
        do = make_do(status=DeliveryStatus.PLANNING)
        with pytest.raises(InvalidStateTransitionError, match="pickup_date"):
            assert_can_transition(
                ctx(do, [make_leg(status=LegStatus.PENDING, pickup_date=None)]),
                DeliveryStatus.DISPATCHED,
            )


# ── 3) DISPATCHED → YARD_STAGED ────────────────────────────────────
class TestDispatchedToYardStaged:
    def _do(self):
        return make_do(status=DeliveryStatus.DISPATCHED)

    def test_requires_first_leg_completed(self):
        with pytest.raises(InvalidStateTransitionError, match="first leg COMPLETED"):
            assert_can_transition(
                ctx(self._do(), [make_leg(status=LegStatus.IN_TRANSIT)]),
                DeliveryStatus.YARD_STAGED,
            )

    def test_requires_yard_kind(self):
        with pytest.raises(InvalidStateTransitionError, match="YARD"):
            assert_can_transition(
                ctx(self._do(), [make_leg()], delivery_loc=LocationKind.CUSTOMER),
                DeliveryStatus.YARD_STAGED,
            )

    def test_happy_path(self):
        assert_can_transition(
            ctx(self._do(), [make_leg()], delivery_loc=LocationKind.YARD),
            DeliveryStatus.YARD_STAGED,
        )


# ── 4) DISPATCHED → FINAL_DELIVERY ─────────────────────────────────
class TestDispatchedToFinalDelivery:
    def _do(self, **kw):
        return make_do(status=DeliveryStatus.DISPATCHED, **kw)

    def test_requires_customer_kind(self):
        with pytest.raises(InvalidStateTransitionError, match="CUSTOMER"):
            assert_can_transition(
                ctx(self._do(), [make_leg()], delivery_loc=LocationKind.YARD),
                DeliveryStatus.FINAL_DELIVERY,
            )

    def test_requires_delivery_appointment(self):
        with pytest.raises(InvalidStateTransitionError, match="delivery_appointment"):
            assert_can_transition(
                ctx(self._do(delivery_appointment=None), [make_leg()],
                    delivery_loc=LocationKind.CUSTOMER),
                DeliveryStatus.FINAL_DELIVERY,
            )

    def test_happy_path(self):
        assert_can_transition(
            ctx(self._do(), [make_leg()], delivery_loc=LocationKind.CUSTOMER),
            DeliveryStatus.FINAL_DELIVERY,
        )


# ── 5) FINAL_DELIVERY → COMPLETED ──────────────────────────────────
class TestFinalDeliveryToCompleted:
    def _do(self, **kw):
        return make_do(status=DeliveryStatus.FINAL_DELIVERY, **kw)

    def test_requires_completed_leg(self):
        with pytest.raises(InvalidStateTransitionError, match="반납 Leg COMPLETED"):
            assert_can_transition(ctx(self._do(), []), DeliveryStatus.COMPLETED)

    def test_requires_return_location(self):
        with pytest.raises(InvalidStateTransitionError, match="return_location"):
            assert_can_transition(
                ctx(self._do(return_location_id=None), [make_leg()]),
                DeliveryStatus.COMPLETED,
            )

    def test_import_requires_empty_date(self):
        do = self._do(direction=ShipmentDirection.IMPORT, empty_date=None)
        with pytest.raises(InvalidStateTransitionError, match="empty_date"):
            assert_can_transition(ctx(do, [make_leg()]), DeliveryStatus.COMPLETED)

    def test_export_requires_loaded_date(self):
        do = self._do(direction=ShipmentDirection.EXPORT,
                      loaded_date=None, empty_date=None)
        with pytest.raises(InvalidStateTransitionError, match="loaded_date"):
            assert_can_transition(ctx(do, [make_leg()]), DeliveryStatus.COMPLETED)

    def test_happy_path_import(self):
        assert_can_transition(ctx(self._do(), [make_leg()]),
                              DeliveryStatus.COMPLETED)

    def test_happy_path_export(self):
        do = self._do(direction=ShipmentDirection.EXPORT,
                      loaded_date=date(2026, 5, 1), empty_date=None)
        assert_can_transition(ctx(do, [make_leg()]), DeliveryStatus.COMPLETED)
