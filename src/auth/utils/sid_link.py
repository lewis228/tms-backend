# src/auth/utils/sid_link.py
from __future__ import annotations
import base64, hmac, time
from hashlib import sha256
from common.const.settings import settings

def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

def _b64url_to_bytes(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def make_sid_signature(sid: str, ts: int) -> str:
    """
    서버 비밀키(SECRET_KEY)로 sid와 ts를 HMAC-SHA256 서명하여 base64url 로 돌려줌.
    """
    msg = f"{sid}.{ts}".encode()
    key = settings.SECRET_KEY.encode()
    return _b64url(hmac.new(key, msg, sha256).digest())

def verify_sid_signature(sid: str, ts: int, sig: str) -> bool:
    """
    링크로 온 sid/sig/ts가 유효한지 검증. (서명만 확인)
    """
    msg = f"{sid}.{ts}".encode()
    key = settings.SECRET_KEY.encode()
    expected = hmac.new(key, msg, sha256).digest()
    try:
        given = _b64url_to_bytes(sig)
    except Exception:
        return False
    return hmac.compare_digest(expected, given)

def is_ts_fresh(
    ts: int,
    *,
    now: int | None = None,
    max_age_sec: int | None = None,
    clock_skew_sec: int | None = None,
) -> bool:
    """
    ts 가 현재 시각 기준 max_age 이내인지 확인. 시계 오차(clock skew) 허용.
    기본값은 settings에서 가져온다.
    """
    max_age = max_age_sec if max_age_sec is not None else settings.SID_LINK_MAX_AGE
    skew    = clock_skew_sec if clock_skew_sec is not None else settings.SID_LINK_CLOCK_SKEW

    n = now or int(time.time())
    if ts > n + skew:
        return False
    return (n - ts) <= max_age
