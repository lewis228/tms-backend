# tests/unit/test_v3_policies.py
"""v3 핵심 정책 unit 테스트 (DB 없음).

- Snapshot Freeze: LegRate.base_amount = flat + per_value × distance + per_min × duration
- ContainerState 자동 derive 규칙
- Charge Code Category enum
- Move Type V3 매핑
"""
from __future__ import annotations
from decimal import Decimal
from types import SimpleNamespace

import pytest

from leg.const.status import (
    StopRole, ContainerState, MoveTypeV3, LegRateSource, HandoverReason,
    DistanceProvider, LegStatus,
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
    """seed_demo 의 derive 로직과 같은 규칙 (간이판). 실제 운영 로직 검증용."""
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
# LegRate Snapshot 계산식
# ────────────────────────────────────────────────────────────────────
def calc_base_tariff(*, flat_base, per_value, per_min, distance, duration_min):
    """Snapshot Always Freeze 정책의 핵심 산식."""
    return Decimal(flat_base) + Decimal(per_value) * Decimal(distance) + Decimal(per_min) * Decimal(duration_min)


def test_tariff_calc_basic():
    """예시: 부산항 → 서울 410km, 300분, per_value=1000, per_min=50, flat=50000."""
    base = calc_base_tariff(
        flat_base=50000, per_value=1000, per_min=50,
        distance=410, duration_min=300,
    )
    assert base == Decimal(50_000 + 1_000 * 410 + 50 * 300)
    assert base == Decimal(475_000)


def test_tariff_calc_traffic_jam():
    """정체로 시간만 늘어나도 per_min 만큼 차이."""
    base_normal = calc_base_tariff(
        flat_base=50000, per_value=1000, per_min=50,
        distance=420, duration_min=300,
    )
    base_jam = calc_base_tariff(
        flat_base=50000, per_value=1000, per_min=50,
        distance=420, duration_min=480,
    )
    assert base_jam - base_normal == Decimal(50 * 180)


def test_tariff_calc_short_distance_flat_base_floor():
    """짧은 거리에도 flat_base 최소 보장."""
    base = calc_base_tariff(
        flat_base=50000, per_value=1000, per_min=50,
        distance=5, duration_min=15,
    )
    # 50000 + 5000 + 750 = 55750
    assert base == Decimal(55_750)
    assert base >= Decimal(50_000)  # flat_base floor


def test_tariff_zero_per_min_only_distance():
    base = calc_base_tariff(
        flat_base=0, per_value=1200, per_min=0, distance=410, duration_min=999,
    )
    # per_min 0 이면 시간 무관
    assert base == Decimal(1_200 * 410)


# ────────────────────────────────────────────────────────────────────
# Snapshot Freeze 정책 — 마스터 변경 후 LegRate 불변
# ────────────────────────────────────────────────────────────────────
class FrozenLegRate(SimpleNamespace):
    """LegRate snapshot — set 후 변경 불가 시뮬레이션."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._frozen = True

    def __setattr__(self, k, v):
        if getattr(self, "_frozen", False) and k in {
            "snapshot_per_value", "snapshot_flat_base", "snapshot_distance_value",
            "base_amount",
        }:
            raise AttributeError(f"snapshot field {k} is frozen")
        super().__setattr__(k, v)


def test_legrate_snapshot_frozen_after_create():
    rate = FrozenLegRate(
        snapshot_per_value=Decimal("1000"),
        snapshot_flat_base=Decimal("50000"),
        snapshot_distance_value=Decimal("410"),
        base_amount=Decimal("475000"),
    )
    # 마스터 RateTariff.per_value 가 1300 으로 변경되어도 LegRate.snapshot 은 그대로
    with pytest.raises(AttributeError):
        rate.snapshot_per_value = Decimal("1300")
    assert rate.snapshot_per_value == Decimal("1000")
    assert rate.base_amount == Decimal("475000")


# ────────────────────────────────────────────────────────────────────
# RateQuote vs RateTariff lookup 우선순위
# ────────────────────────────────────────────────────────────────────
def lookup_rate_source(*, has_quote_match: bool, has_tariff_match: bool, has_distance: bool):
    """leg_rate.service.compute() 의 매칭 우선순위 시뮬레이션."""
    if has_quote_match:
        return LegRateSource.QUOTE_FIXED
    if has_tariff_match:
        if has_distance:
            return LegRateSource.TARIFF_CALC
        return LegRateSource.TARIFF_FLAT
    return LegRateSource.NONE


def test_quote_takes_priority_over_tariff():
    s = lookup_rate_source(has_quote_match=True, has_tariff_match=True, has_distance=True)
    assert s == LegRateSource.QUOTE_FIXED


def test_tariff_calc_when_distance_present():
    s = lookup_rate_source(has_quote_match=False, has_tariff_match=True, has_distance=True)
    assert s == LegRateSource.TARIFF_CALC


def test_tariff_flat_when_no_distance():
    """거리 미등록이면 flat_base 만 사용 (TARIFF_FLAT)."""
    s = lookup_rate_source(has_quote_match=False, has_tariff_match=True, has_distance=False)
    assert s == LegRateSource.TARIFF_FLAT


def test_none_when_neither_matches():
    s = lookup_rate_source(has_quote_match=False, has_tariff_match=False, has_distance=True)
    assert s == LegRateSource.NONE


# ────────────────────────────────────────────────────────────────────
# LegCharge 자동 amount 계산 (snapshot_unit_amount × quantity)
# ────────────────────────────────────────────────────────────────────
def test_leg_charge_amount_qty_times_unit():
    """대기 (10분당) ₩10,000 × qty 4 = ₩40,000."""
    snapshot_unit_amount = Decimal("10000")
    quantity = Decimal("4")
    amount = snapshot_unit_amount * quantity
    assert amount == Decimal("40000")


def test_leg_charge_negative_quantity_for_penalty():
    """기사 과실 페널티 — signed=true 라 음수 입력 가능."""
    snapshot_unit_amount = Decimal("-50000")
    quantity = Decimal("1")
    amount = snapshot_unit_amount * quantity
    assert amount == Decimal("-50000")


# ────────────────────────────────────────────────────────────────────
# ChargeCategory enum
# ────────────────────────────────────────────────────────────────────
def test_charge_category_v3_values():
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
# DistanceProvider
# ────────────────────────────────────────────────────────────────────
def test_distance_provider_values():
    assert {p.value for p in DistanceProvider} == {
        "OSRM", "GOOGLE", "MANUAL", "CACHED",
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
