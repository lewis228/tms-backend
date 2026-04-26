# src/auth/oauth/google.py
from __future__ import annotations
import httpx
from redis.asyncio import Redis

from auth.const.providers import AuthProviderEnum
from auth.oauth.base import OAuthProviderBase, OAuthUserInfo
from common.const.settings import settings
from common.exceptions.base import AppException


class GoogleOAuthProvider(OAuthProviderBase):
    """
    Google OAuth 2.0 구현.
    
    문서: https://developers.google.com/identity/protocols/oauth2/web-server
    
    필요한 스코프:
    - openid: OpenID Connect
    - email: 이메일 주소
    - profile: 이름, 프로필 사진
    """
    
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
        """Google 전용 추가 파라미터"""
        return {
            "access_type": "offline",  # refresh_token 받기
            "prompt": "consent",       # 항상 동의 화면 표시 (refresh_token 보장)
        }
    
    async def exchange_code_for_token(self, code: str) -> dict:
        """
        인증 코드를 토큰으로 교환.
        
        Returns:
            {
                "access_token": "...",
                "expires_in": 3600,
                "refresh_token": "...",  # 첫 인증 시에만
                "scope": "openid email profile",
                "token_type": "Bearer",
                "id_token": "..."  # JWT
            }
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        
        if response.status_code != 200:
            raise AppException(
                code="GOOGLE_TOKEN_ERROR",
                message="Google 토큰 교환에 실패했습니다.",
                status_code=400,
                detail={"error": response.text},
            )
        
        return response.json()
    
    async def get_user_info(self, token_response: dict) -> OAuthUserInfo:
        """
        Google 사용자 정보 조회.
        
        userinfo 응답 예시:
        {
            "sub": "123456789",  # Google 고유 ID
            "name": "홍길동",
            "given_name": "길동",
            "family_name": "홍",
            "picture": "https://...",
            "email": "user@gmail.com",
            "email_verified": true,
            "locale": "ko"
        }
        """
        access_token = token_response.get("access_token")
        if not access_token:
            raise AppException(
                code="GOOGLE_NO_TOKEN",
                message="Google 액세스 토큰이 없습니다.",
                status_code=400,
            )
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        
        if response.status_code != 200:
            raise AppException(
                code="GOOGLE_USERINFO_ERROR",
                message="Google 사용자 정보 조회에 실패했습니다.",
                status_code=400,
                detail={"error": response.text},
            )
        
        data = response.json()
        
        return OAuthUserInfo(
            provider=AuthProviderEnum.GOOGLE,
            oauth_id=data["sub"],
            email=data.get("email"),
            name=data.get("name"),
            profile_image=data.get("picture"),
        )