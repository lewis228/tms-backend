# common/utils/time.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def utc_ts() -> int:
    """현재 UTC 시간을 Unix timestamp(초 단위)로 반환"""
    return int(utc_now().timestamp())

def exp_in(seconds: int) -> int:
    """지금으로부터 seconds 뒤의 Unix timestamp(초 단위)로 반환"""
    return int((utc_now() + timedelta(seconds=seconds)).timestamp())
