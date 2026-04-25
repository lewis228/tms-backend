import uuid
import secrets

def new_id() -> str:
    return uuid.uuid4().hex

def new_token_id(nbytes: int = 16) -> str:
    return secrets.token_urlsafe(nbytes)
