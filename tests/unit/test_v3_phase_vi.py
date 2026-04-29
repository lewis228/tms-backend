# tests/unit/test_v3_phase_vi.py
"""Phase VI 산식·라우트 sanity (DB 없이)."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from math import ceil


# ────────────────────────────────────────────────────────────────────
# B.6 — WAITING qty 산출 (auto_waiting_on_complete 와 같은 산식)
# ────────────────────────────────────────────────────────────────────
def waiting_qty_buckets(arrival: datetime | None, departure: datetime | None,
                        bucket_min: int = 10) -> int:
    if arrival is None or departure is None:
        return 0
    delta = departure - arrival
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes <= 0:
        return 0
    return ceil(minutes / bucket_min)


def test_waiting_zero_when_no_times():
    assert waiting_qty_buckets(None, None) == 0


def test_waiting_zero_when_negative():
    a = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    d = a - timedelta(minutes=5)
    assert waiting_qty_buckets(a, d) == 0


def test_waiting_25_min_to_3_buckets():
    a = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    d = a + timedelta(minutes=25)
    # ceil(25/10) = 3
    assert waiting_qty_buckets(a, d) == 3


def test_waiting_exactly_30_min_to_3_buckets():
    a = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    d = a + timedelta(minutes=30)
    assert waiting_qty_buckets(a, d) == 3


def test_waiting_31_min_to_4_buckets():
    a = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    d = a + timedelta(minutes=31)
    assert waiting_qty_buckets(a, d) == 4


def test_waiting_amount_qty_times_unit():
    qty = waiting_qty_buckets(
        datetime(2026, 4, 29, 12, tzinfo=timezone.utc),
        datetime(2026, 4, 29, 12, 40, tzinfo=timezone.utc),
    )
    assert qty == 4
    unit = Decimal("10000")
    assert unit * qty == Decimal("40000")


# ────────────────────────────────────────────────────────────────────
# B.10 — Demurrage 적용 조건 (서비스의 if 분기와 같은 규칙)
# ────────────────────────────────────────────────────────────────────
def is_demurrage_applicable(*, lfd, today, has_active_leg: bool,
                            charge_code_present: bool) -> bool:
    if not charge_code_present:
        return False
    if not has_active_leg:
        return False
    if lfd is None:
        return False
    return lfd < today


def test_demurrage_applies_when_lfd_past_and_active():
    from datetime import date
    assert is_demurrage_applicable(
        lfd=date(2026, 4, 28), today=date(2026, 4, 29),
        has_active_leg=True, charge_code_present=True,
    )


def test_demurrage_not_applies_today_lfd():
    from datetime import date
    assert not is_demurrage_applicable(
        lfd=date(2026, 4, 29), today=date(2026, 4, 29),
        has_active_leg=True, charge_code_present=True,
    )


def test_demurrage_skipped_when_no_active_leg():
    from datetime import date
    assert not is_demurrage_applicable(
        lfd=date(2026, 4, 28), today=date(2026, 4, 29),
        has_active_leg=False, charge_code_present=True,
    )


def test_demurrage_skipped_when_charge_code_missing():
    from datetime import date
    assert not is_demurrage_applicable(
        lfd=date(2026, 4, 28), today=date(2026, 4, 29),
        has_active_leg=True, charge_code_present=False,
    )


# ────────────────────────────────────────────────────────────────────
# B.5 — Stop reorder 의 sequence 재배열 — arrayMove 로직
# ────────────────────────────────────────────────────────────────────
def array_move(items: list, old_idx: int, new_idx: int) -> list:
    out = items[:]
    item = out.pop(old_idx)
    out.insert(new_idx, item)
    return out


def test_array_move_top_to_bottom():
    items = ["A", "B", "C", "D"]
    assert array_move(items, 0, 3) == ["B", "C", "D", "A"]


def test_array_move_bottom_to_top():
    items = ["A", "B", "C", "D"]
    assert array_move(items, 3, 0) == ["D", "A", "B", "C"]


def test_array_move_no_op():
    items = ["A", "B", "C"]
    assert array_move(items, 1, 1) == items


# ────────────────────────────────────────────────────────────────────
# B.9 — 정산 리포트 합계 산식
# ────────────────────────────────────────────────────────────────────
def report_grand_total(legs: list[dict]) -> Decimal:
    base = sum((Decimal(l["base_amount"]) for l in legs), Decimal("0"))
    charges = sum((Decimal(l["charges_total"]) for l in legs), Decimal("0"))
    return base + charges


def test_settlement_grand_total():
    legs = [
        {"base_amount": "300000", "charges_total": "40000"},
        {"base_amount": "150000", "charges_total": "0"},
        {"base_amount": "200000", "charges_total": "-50000"},  # 페널티
    ]
    assert report_grand_total(legs) == Decimal("640000")


# ────────────────────────────────────────────────────────────────────
# B.7 — driver_mobile v3 stop arrive/depart fill 규칙
# ────────────────────────────────────────────────────────────────────
def fill_stop_times(*, current_arrival, current_departure,
                    is_arrive: bool, when):
    """report_stop_arrive / depart 의 채움 규칙."""
    arrival = current_arrival
    departure = current_departure
    if is_arrive:
        if arrival is None:
            arrival = when
    else:
        if arrival is None:  # 도착 누락 — 동시 채움
            arrival = when
        if departure is None:
            departure = when
    return arrival, departure


def test_arrive_fills_only_arrival_when_missing():
    a, d = fill_stop_times(
        current_arrival=None, current_departure=None,
        is_arrive=True, when=datetime(2026, 4, 29, 12, tzinfo=timezone.utc),
    )
    assert a == datetime(2026, 4, 29, 12, tzinfo=timezone.utc)
    assert d is None


def test_arrive_does_not_overwrite_existing_arrival():
    earlier = datetime(2026, 4, 29, 11, tzinfo=timezone.utc)
    a, d = fill_stop_times(
        current_arrival=earlier, current_departure=None,
        is_arrive=True, when=datetime(2026, 4, 29, 12, tzinfo=timezone.utc),
    )
    assert a == earlier  # 기존값 유지


def test_depart_fills_both_when_arrival_missing():
    when = datetime(2026, 4, 29, 13, tzinfo=timezone.utc)
    a, d = fill_stop_times(
        current_arrival=None, current_departure=None,
        is_arrive=False, when=when,
    )
    assert a == when and d == when


def test_depart_only_fills_departure_when_arrival_present():
    a0 = datetime(2026, 4, 29, 12, tzinfo=timezone.utc)
    when = datetime(2026, 4, 29, 13, tzinfo=timezone.utc)
    a, d = fill_stop_times(
        current_arrival=a0, current_departure=None,
        is_arrive=False, when=when,
    )
    assert a == a0
    assert d == when
