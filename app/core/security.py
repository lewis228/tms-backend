"""bcrypt + JWT + 임시 비밀번호 발급.

- access TTL: settings.access_ttl_minutes
- refresh TTL: settings.refresh_ttl_days
- claim: sub(user_id), tenant_id, role, type(access|refresh), exp, iat
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import settings
from app.core.exceptions import UnauthorizedError

_ALG = "HS256"


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_temp_password(length: int = 12) -> str:
    """Driver 임시 비번. 영대소문자+숫자+기호 1개 이상 보장."""
    if length < 8:
        length = 8
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length - 1))
        pw += secrets.choice("!@#$%^&*")
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
        ):
            return pw


def _encode(payload: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": int(now.timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALG)


def create_access_token(*, user_id: str, tenant_id: str | None, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_ttl_minutes)
    return _encode(
        {
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "type": "access",
            "exp": int(exp.timestamp()),
        }
    )


def create_refresh_token(*, user_id: str, tenant_id: str | None, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=settings.refresh_ttl_days)
    return _encode(
        {
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "type": "refresh",
            "exp": int(exp.timestamp()),
        }
    )


def decode_token(token: str, *, expected_type: str = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALG])
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedError("Token expired", code="ERR_TOKEN_EXPIRED") from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedError("Invalid token", code="ERR_TOKEN_INVALID") from e
    if payload.get("type") != expected_type:
        raise UnauthorizedError("Wrong token type", code="ERR_TOKEN_TYPE")
    return payload
