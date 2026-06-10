# tests/unit/test_v3_policies.py
"""컨테이너/leg enum 정책 unit 테스트 (DB 없음).

- ContainerState 8단계 자동 derive 규칙
- MoveTypeV3 매핑
- ChargeCategory / HandoverReason / StopRole / LegStatus enum
"""
from __future__ import annotations

from leg.const.status import (
    StopRole, ContainerState, MoveTypeV3, HandoverReason, LegStatus,
)
from charge_code.const.status import ChargeCategory


# ────────────────────────────────────────────────────────────────────
# StopRole
# ────────────────────────────────────────────────────────────────────
def test_stop_role_values():
    assert StopRole.ORIGIN.value == "ORIGIN"
    assert StopRole.DELIVERY.value == "DELIVERY"
    assert StopRole.TRANSIT.value == "TRANSIT"
    assert StopRole.TERMINUS.value == "TERMINUS"


# ────────────────────────────────────────────────────────────────────
# ContainerState 8단계
# ────────────────────────────────────────────────────────────────────
def test_container_state_8_values():
    states = {s.value for s in ContainerState}
    assert states == {
        "DRAFT", "PLANNED", "IN_TRANSIT", "AT_STOP",
        "WAITING_PLAN", "HOLD", "COMPLETED", "CANCELLED",
    }


def derive_container_state(*, stops_count, all_legs_pending, has_in_transit_leg,
                           last_stop_actual_arrival, last_stop_has_next_leg,
                           all_completed_terminus_arrived,
                           hold=False, cancelled=False):
    """container.state_derive 의 derive 규칙(간이판). 운영 derive 로직 검증용."""
    if cancelled:
        return ContainerState.CANCELLED
    if hold:
        return ContainerState.HOLD
    if stops_count == 0:
        return ContainerState.DRAFT
    if all_completed_terminus_arrived:
        return ContainerState.COMPLETED
    if has_in_transit_leg:
        return ContainerState.IN_TRANSIT
    if last_stop_actual_arrival and not last_stop_has_next_leg:
        return ContainerState.WAITING_PLAN
    if last_stop_actual_arrival and last_stop_has_next_leg:
        return ContainerState.AT_STOP
    if all_legs_pending:
        return ContainerState.PLANNED
    return ContainerState.PLANNED


def test_state_draft_when_no_stops():
    s = derive_container_state(
        stops_count=0, all_legs_pending=False, has_in_transit_leg=False,
        last_stop_actual_arrival=False, last_stop_has_next_leg=False,
        all_completed_terminus_arrived=False,
    )
    assert s == ContainerState.DRAFT


def test_state_planned_when_legs_pending():
    s = derive_container_state(
        stops_count=2, all_legs_pending=True, has_in_transit_leg=False,
        last_stop_actual_arrival=False, last_stop_has_next_leg=False,
        all_completed_terminus_arrived=False,
    )
    assert s == ContainerState.PLANNED


def test_state_in_transit():
    s = derive_container_state(
        stops_count=3, all_legs_pending=False, has_in_transit_leg=True,
        last_stop_actual_arrival=False, last_stop_has_next_leg=True,
        all_completed_terminus_arrived=False,
    )
    assert s == ContainerState.IN_TRANSIT


def test_state_waiting_plan_warning():
    """⚠️ 마지막 plan 된 stop 도착 + 다음 leg 미생성 → WAITING_PLAN."""
    s = derive_container_state(
        stops_count=2, all_legs_pending=False, has_in_transit_leg=False,
        last_stop_actual_arrival=True, last_stop_has_next_leg=False,
        all_completed_terminus_arrived=False,
    )
    assert s == ContainerState.WAITING_PLAN


def test_state_at_stop_when_next_leg_pending():
    s = derive_container_state(
        stops_count=3, all_legs_pending=False, has_in_transit_leg=False,
        last_stop_actual_arrival=True, last_stop_has_next_leg=True,
        all_completed_terminus_arrived=False,
    )
    assert s == ContainerState.AT_STOP


def test_state_completed():
    s = derive_container_state(
        stops_count=3, all_legs_pending=False, has_in_transit_leg=False,
        last_stop_actual_arrival=True, last_stop_has_next_leg=False,
        all_completed_terminus_arrived=True,
    )
    assert s == ContainerState.COMPLETED


def test_state_hold_overrides_others():
    s = derive_container_state(
        stops_count=3, all_legs_pending=False, has_in_transit_leg=True,
        last_stop_actual_arrival=False, last_stop_has_next_leg=True,
        all_completed_terminus_arrived=False, hold=True,
    )
    assert s == ContainerState.HOLD


def test_state_cancelled_overrides_others():
    s = derive_container_state(
        stops_count=3, all_legs_pending=False, has_in_transit_leg=True,
        last_stop_actual_arrival=False, last_stop_has_next_leg=True,
        all_completed_terminus_arrived=False, hold=True, cancelled=True,
    )
    assert s == ContainerState.CANCELLED


# ────────────────────────────────────────────────────────────────────
# MoveTypeV3 + 기존 매핑
# ────────────────────────────────────────────────────────────────────
def test_move_type_v3_4_values():
    assert {m.value for m in MoveTypeV3} == {
        "TRUCK_ONLY", "CHASSIS_ONLY", "EMPTY_LOADED", "FULL_LOADED",
    }


def map_legacy_move_type(legacy: str) -> str:
    return {"LOADED": "FULL_LOADED", "EMPTY": "EMPTY_LOADED", "BOBTAIL": "TRUCK_ONLY"}[legacy]


def test_legacy_move_type_mapping():
    assert map_legacy_move_type("LOADED") == "FULL_LOADED"
    assert map_legacy_move_type("EMPTY") == "EMPTY_LOADED"
    assert map_legacy_move_type("BOBTAIL") == "TRUCK_ONLY"


# ────────────────────────────────────────────────────────────────────
# ChargeCategory enum
# ────────────────────────────────────────────────────────────────────
def test_charge_category_values():
    assert {c.value for c in ChargeCategory} == {
        "BASE", "WAITING", "EXTRA_STOP", "DRY_RUN",
        "PENALTY", "SURCHARGE", "ADJUSTMENT", "OTHER",
    }


# ────────────────────────────────────────────────────────────────────
# HandoverReason
# ────────────────────────────────────────────────────────────────────
def test_handover_reason_values():
    assert {r.value for r in HandoverReason} == {
        "TERMINAL_CLOSED", "ACCIDENT", "SHIFT_CHANGE", "OTHER",
    }


# ────────────────────────────────────────────────────────────────────
# LegStatus 기본 (sanity)
# ────────────────────────────────────────────────────────────────────
def test_leg_status_basic_set():
    statuses = {s.value for s in LegStatus}
    assert "PENDING" in statuses
    assert "IN_TRANSIT" in statuses
    assert "COMPLETED" in statuses
    assert "FAILED" in statuses
