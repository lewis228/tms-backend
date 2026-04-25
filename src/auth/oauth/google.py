from __future__ import annotations
import httpx
from redis.asyncio import Redis
from auth.const.providers import AuthProviderEnum
from auth.oauth.base import OAuthProviderBase, OAuthUserInfo
from common.const.settings import settings
from common.exceptions.base import AppException


class GoogleOAuthProvider(OAuthProviderBase):
    def __init__(self, redis: Redis):
        super().__init__(redis)

    @property
    def provider(self) -> AuthProviderEnum:
        return AuthProviderEnum.GOOGLE
    @property
    def authorization_url(self) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth"
    @property
    def token_url(self) -> str:
        return "https://oauth2.googleapis.com/token"
    @property
    def userinfo_url(self) -> str:
        return "https://www.googleapis.com/oauth2/v3/userinfo"
    @property
    def client_id(self) -> str:
        return settings.GOOGLE_CLIENT_ID
    @property
    def client_secret(self) -> str:
        return settings.GOOGLE_CLIENT_SECRET
    @property
    def redirect_uri(self) -> str:
        return settings.GOOGLE_REDIRECT_URI
    @property
    def scopes(self) -> list[str]:
        return ["openid", "email", "profile"]

    def _extra_auth_params(self) -> dict:
        return {"access_type": "offline", "prompt": "consent"}

    async def exchange_code_for_token(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "code": code, "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code != 200:
            raise AppException(code="GOOGLE_TOKEN_ERROR", message="Google 토큰 교환에 실패했습니다.", status_code=400)
        return response.json()

    async def get_user_info(self, token_response: dict) -> OAuthUserInfo:
        access_token = token_response.get("access_token")
        if not access_token:
            raise AppException(code="GOOGLE_NO_TOKEN", message="Google 액세스 토큰이 없습니다.", status_code=400)
        async with httpx.AsyncClient() as client:
            response = await client.get(self.userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            raise AppException(code="GOOGLE_USERINFO_ERROR", message="Google 사용자 정보 조회에 실패했습니다.", status_code=400)
        data = response.json()
        return OAuthUserInfo(
            provider=AuthProviderEnum.GOOGLE,
            oauth_id=data["sub"],
            email=data.get("email"),
            name=data.get("name"),
            profile_image=data.get("picture"),
        )
