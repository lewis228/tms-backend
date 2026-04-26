# common/utils/ids.py
import uuid
import secrets

def new_id() -> str:
    """충돌 가능성이 매우 낮은 32hex ID (UUID4)."""
    return uuid.uuid4().hex

def new_token_id(nbytes: int = 16) -> str:
    """URL-safe 난수 ID (jti 등에 권장)."""
    return secrets.token_urlsafe(nbytes)
