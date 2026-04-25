from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import secrets
from redis.asyncio import Redis
from auth.const.providers import AuthProviderEnum
from common.const.settings import settings, OAUTH_STATE_TTL


@dataclass
class OAuthUserInfo:
    provider: AuthProviderEnum
    oauth_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    profile_image: Optional[str] = None


class OAuthProviderBase(ABC):
    def __init__(self, redis: Redis):
        self.redis = redis

    @property
    @abstractmethod
    def provider(self) -> AuthProviderEnum: ...
    @property
    @abstractmethod
    def authorization_url(self) -> str: ...
    @property
    @abstractmethod
    def token_url(self) -> str: ...
    @property
    @abstractmethod
    def userinfo_url(self) -> str: ...
    @property
    @abstractmethod
    def client_id(self) -> str: ...
    @property
    @abstractmethod
    def client_secret(self) -> str: ...
    @property
    @abstractmethod
    def redirect_uri(self) -> str: ...
    @property
    @abstractmethod
    def scopes(self) -> list[str]: ...

    async def generate_state(self) -> str:
        state = secrets.token_urlsafe(32)
        key = f"oauth_state:{self.provider.value}:{state}"
        await self.redis.set(key, "1", ex=OAUTH_STATE_TTL)
        return state

    async def verify_state(self, state: str) -> bool:
        key = f"oauth_state:{self.provider.value}:{state}"
        result = await self.redis.get(key)
        if result:
            await self.redis.delete(key)
            return True
        return False

    async def get_authorization_url(self) -> tuple[str, str]:
        state = await self.generate_state()
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
        }
        params.update(self._extra_auth_params())
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.authorization_url}?{query}"
        return url, state

    def _extra_auth_params(self) -> dict:
        return {}

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> dict: ...
    @abstractmethod
    async def get_user_info(self, token_response: dict) -> OAuthUserInfo: ...

    async def authenticate(self, code: str, state: str) -> OAuthUserInfo:
        if not await self.verify_state(state):
            raise ValueError("Invalid or expired state parameter")
        token_response = await self.exchange_code_for_token(code)
        return await self.get_user_info(token_response)
