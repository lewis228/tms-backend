# src/auth/oauth/kakao.py
from __future__ import annotations
import httpx
from redis.asyncio import Redis

from auth.const.providers import AuthProviderEnum
from auth.oauth.base import OAuthProviderBase, OAuthUserInfo
from common.const.settings import settings
from common.exceptions.base import AppException


class KakaoOAuthProvider(OAuthProviderBase):
    """
    Kakao OAuth 2.0 구현.
    
    문서: https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api
    
    주의사항:
    - 카카오는 이메일이 필수가 아님 (사용자가 동의 안 하면 없음)
    - 카카오 비즈니스 앱 등록 후 이메일 필수 동의 설정 가능
    """
    
    def __init__(self, redis: Redis):
        super().__init__(redis)
    
    @property
    def provider(self) -> AuthProviderEnum:
        return AuthProviderEnum.KAKAO
    
    @property
    def authorization_url(self) -> str:
        return "https://kauth.kakao.com/oauth/authorize"
    
    @property
    def token_url(self) -> str:
        return "https://kauth.kakao.com/oauth/token"
    
    @property
    def userinfo_url(self) -> str:
        return "https://kapi.kakao.com/v2/user/me"
    
    @property
    def client_id(self) -> str:
        return settings.KAKAO_CLIENT_ID
    
    @property
    def client_secret(self) -> str:
        return settings.KAKAO_CLIENT_SECRET
    
    @property
    def redirect_uri(self) -> str:
        return settings.KAKAO_REDIRECT_URI
    
    @property
    def scopes(self) -> list[str]:
        # 카카오 동의항목 ID
        # - profile_nickname: 닉네임
        # - profile_image: 프로필 사진
        # - account_email: 이메일 (비즈 앱만 필수 설정 가능)
        return ["profile_nickname", "profile_image", "account_email"]
    
    async def exchange_code_for_token(self, code: str) -> dict:
        """
        인증 코드를 토큰으로 교환.
        
        Returns:
            {
                "access_token": "...",
                "token_type": "bearer",
                "refresh_token": "...",
                "expires_in": 21599,
                "scope": "account_email profile_image profile_nickname",
                "refresh_token_expires_in": 5183999
            }
        """
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        
        # client_secret이 있으면 추가 (선택 사항)
        if self.client_secret:
            data["client_secret"] = self.client_secret
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        
        if response.status_code != 200:
            raise AppException(
                code="KAKAO_TOKEN_ERROR",
                message="카카오 토큰 교환에 실패했습니다.",
                status_code=400,
                detail={"error": response.text},
            )
        
        return response.json()
    
    async def get_user_info(self, token_response: dict) -> OAuthUserInfo:
        """
        Kakao 사용자 정보 조회.
        
        응답 예시:
        {
            "id": 123456789,  # 카카오 고유 ID
            "connected_at": "2024-01-01T00:00:00Z",
            "properties": {
                "nickname": "홍길동",
                "profile_image": "https://...",
                "thumbnail_image": "https://..."
            },
            "kakao_account": {
                "profile_nickname_needs_agreement": false,
                "profile_image_needs_agreement": false,
                "profile": {
                    "nickname": "홍길동",
                    "thumbnail_image_url": "https://...",
                    "profile_image_url": "https://...",
                    "is_default_image": false
                },
                "has_email": true,
                "email_needs_agreement": false,
                "is_email_valid": true,
                "is_email_verified": true,
                "email": "user@example.com"
            }
        }
        """
        access_token = token_response.get("access_token")
        if not access_token:
            raise AppException(
                code="KAKAO_NO_TOKEN",
                message="카카오 액세스 토큰이 없습니다.",
                status_code=400,
            )
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.userinfo_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                },
            )
        
        if response.status_code != 200:
            raise AppException(
                code="KAKAO_USERINFO_ERROR",
                message="카카오 사용자 정보 조회에 실패했습니다.",
                status_code=400,
                detail={"error": response.text},
            )
        
        data = response.json()
        
        # 카카오 고유 ID (숫자)
        oauth_id = str(data["id"])
        
        # 이메일 (없을 수 있음)
        kakao_account = data.get("kakao_account", {})
        email = kakao_account.get("email")
        
        # 프로필 정보
        profile = kakao_account.get("profile", {})
        name = profile.get("nickname")
        profile_image = profile.get("profile_image_url")
        
        # properties에서도 가져올 수 있음 (fallback)
        properties = data.get("properties", {})
        if not name:
            name = properties.get("nickname")
        if not profile_image:
            profile_image = properties.get("profile_image")
        
        return OAuthUserInfo(
            provider=AuthProviderEnum.KAKAO,
            oauth_id=oauth_id,
            email=email,  # 없을 수 있음!
            name=name,
            profile_image=profile_image,
        )