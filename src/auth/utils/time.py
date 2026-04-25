from __future__ import annotations
from datetime import datetime, timedelta, timezone

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def utc_ts() -> int:
    return int(utc_now().timestamp())

def exp_in(seconds: int) -> int:
    return int((utc_now() + timedelta(seconds=seconds)).timestamp())
