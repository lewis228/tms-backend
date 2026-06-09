# src/payroll/periods.py
"""Bi-weekly(격주) 정산 기간 계산 (재설계 2c).

격주 정산은 고정 anchor(기준일)로부터 14일 주기로 끊는다.
anchor 를 바꾸면 회사별 급여 주기에 맞출 수 있다(기본 2024-01-01 월요일).
"""
from __future__ import annotations
from datetime import date, timedelta

# 기본 anchor — 회사 급여주기 기준일. 필요 시 settings 로 빼서 팀별 조정.
DEFAULT_ANCHOR = date(2024, 1, 1)  # Monday
PERIOD_DAYS = 14


def biweekly_period(ref: date, *, anchor: date = DEFAULT_ANCHOR) -> tuple[date, date]:
    """ref 가 속한 격주 기간 [start, end] (둘 다 포함). end = start + 13일."""
    delta = (ref - anchor).days
    # 음수 delta 도 바닥 정렬(floor division)로 정확히 끊김
    index = delta // PERIOD_DAYS
    start = anchor + timedelta(days=index * PERIOD_DAYS)
    end = start + timedelta(days=PERIOD_DAYS - 1)
    return start, end


def next_period(start: date) -> tuple[date, date]:
    """주어진 기간 시작일 다음 격주 기간."""
    nxt = start + timedelta(days=PERIOD_DAYS)
    return nxt, nxt + timedelta(days=PERIOD_DAYS - 1)


def period_index(ref: date, *, anchor: date = DEFAULT_ANCHOR) -> int:
    """anchor 기준 격주 인덱스(0,1,2…). 정산 라벨/정렬용."""
    return (ref - anchor).days // PERIOD_DAYS
