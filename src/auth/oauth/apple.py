# src/auth/oauth/apple.py
from __future__ import annotations
import time
import jwt
import httpx
from redis.asyncio import Redis

from auth.const.providers import AuthProviderEnum
from auth.oauth.base import OAuthProviderBase, OAuthUserInfo
from common.const.settings import settings
from common.exceptions.base import AppException


class AppleOAuthProvider(OAuthProviderBase):
    """
    Apple Sign In 구현.
    
    문서: https://developer.apple.com/documentation/sign_in_with_apple/sign_in_with_apple_rest_api
    
    주의사항:
    - client_secret은 JWT로 동적 생성 (5분마다 갱신 권장)
    - 이메일은 첫 로그인 때만 받을 수 있음 (이후엔 id_token에서만)
    - 사용자가 "이메일 숨기기" 선택 시 relay 이메일 제공
    - 이름은 첫 로그인 때만 user 파라미터로 전달됨
    """
    
    def __init__(self, redis: Redis):
        super().__init__(redis)
        self._client_secret_cache = None
        self._client_secret_exp = 0
    
    @property
    def provider(self) -> AuthProviderEnum:
        return AuthProviderEnum.APPLE
    
    @property
    def authorization_url(self) -> str:
        return "https://appleid.apple.com/auth/authorize"
    
    @property
    def token_url(self) -> str:
        return "https://appleid.apple.com/auth/token"
    
    @property
    def userinfo_url(self) -> str:
        # Apple은 userinfo 엔드포인트가 없음 - id_token에서 추출
        return ""
    
    @property
    def client_id(self) -> str:
        return settings.APPLE_CLIENT_ID
    
    @property
    def client_secret(self) -> str:
        """
        Apple은 client_secret을 JWT로 동적 생성.
        5분 유효, 캐싱하여 재사용.
        """
        now = int(time.time())
        
        # 캐시된 secret이 아직 유효하면 재사용
        if self._client_secret_cache and now < self._client_secret_exp - 60:
            return self._client_secret_cache
        
        # 새 client_secret JWT 생성
        exp = now + 300  # 5분
        
        payload = {
            "iss": settings.APPLE_TEAM_ID,
            "iat": now,
            "exp": exp,
            "aud": "https://appleid.apple.com",
            "sub": settings.APPLE_CLIENT_ID,
        }
        
        headers = {
            "kid": settings.APPLE_KEY_ID,
            "alg": "ES256",
        }
        
        # .p8 파일의 private key
        private_key = settings.APPLE_PRIVATE_KEY
        
        self._client_secret_cache = jwt.encode(
            payload,
            private_key,
            algorithm="ES256",
            headers=headers,
        )
        self._client_secret_exp = exp
        
        return self._client_secret_cache
    
    @property
    def redirect_uri(self) -> str:
        return settings.APPLE_REDIRECT_URI
    
    @property
    def scopes(self) -> list[str]:
        return ["name", "email"]
    
    def _extra_auth_params(self) -> dict:
        """Apple 전용 추가 파라미터"""
        return {
            "response_mode": "form_post",  # Apple은 form_post 권장
        }
    
    async def exchange_code_for_token(self, code: str) -> dict:
        """
        인증 코드를 토큰으로 교환.
        
        Returns:
            {
                "access_token": "...",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "...",
                "id_token": "..."  # JWT - 사용자 정보 포함
            }
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        
        if response.status_code != 200:
            raise AppException(
                code="APPLE_TOKEN_ERROR",
                message="Apple 토큰 교환에 실패했습니다.",
                status_code=400,
                detail={"error": response.text},
            )
        
        return response.json()
    
    async def get_user_info(self, token_response: dict) -> OAuthUserInfo:
        """
        Apple 사용자 정보 조회.
        
        id_token (JWT) 디코딩 결과 예시:
        {
            "iss": "https://appleid.apple.com",
            "aud": "com.binflow.auth",
            "exp": 1234567890,
            "iat": 1234567890,
            "sub": "001234.abcd1234...",  # Apple 고유 ID
            "email": "user@privaterelay.appleid.com",  # 또는 실제 이메일
            "email_verified": "true",
            "is_private_email": "true",  # 이메일 숨기기 사용 시
            "auth_time": 1234567890,
            "nonce_supported": true
        }
        
        주의: 이름은 id_token에 없음! 첫 로그인 시 별도 user 파라미터로만 전달됨.
        """
        id_token = token_response.get("id_token")
        if not id_token:
            raise AppException(
                code="APPLE_NO_ID_TOKEN",
                message="Apple id_token이 없습니다.",
                status_code=400,
            )
        
        # id_token 디코딩 (서명 검증은 생략 - 프로덕션에서는 Apple 공개키로 검증 권장)
        try:
            # 서명 검증 없이 디코딩 (개발용)
            payload = jwt.decode(id_token, options={"verify_signature": False})
        except jwt.InvalidTokenError as e:
            raise AppException(
                code="APPLE_INVALID_TOKEN",
                message="Apple id_token 디코딩에 실패했습니다.",
                status_code=400,
                detail={"error": str(e)},
            )
        
        oauth_id = payload.get("sub")
        if not oauth_id:
            raise AppException(
                code="APPLE_NO_SUB",
                message="Apple 사용자 ID가 없습니다.",
                status_code=400,
            )
        
        email = payload.get("email")
        
        # 이름은 첫 로그인 시에만 user 파라미터로 전달됨
        # token_response에 user 정보가 있으면 사용
        name = None
        user_data = token_response.get("user")
        if user_data and isinstance(user_data, dict):
            name_data = user_data.get("name", {})
            first_name = name_data.get("firstName", "")
            last_name = name_data.get("lastName", "")
            name = f"{last_name}{first_name}".strip() or None
        
        return OAuthUserInfo(
            provider=AuthProviderEnum.APPLE,
            oauth_id=oauth_id,
            email=email,
            name=name,  # 첫 로그인에만 있음
            profile_image=None,  # Apple은 프로필 이미지 제공 안 함
        )
    
    async def authenticate_with_user_data(
        self,
        code: str,
        state: str,
        user_data: dict = None,
    ) -> OAuthUserInfo:
        """
        Apple 인증 (user 파라미터 포함).
        
        Apple은 첫 로그인 시에만 이름을 user 파라미터로 전달하므로,
        별도 메서드로 처리.
        
        Args:
            code: 인증 코드
            state: CSRF 방지용 state
            user_data: Apple이 전달한 user 정보 (첫 로그인 시에만)
        """
        # 1. State 검증
        if not await self.verify_state(state):
            raise ValueError("Invalid or expired state parameter")
        
        # 2. 토큰 교환
        token_response = await self.exchange_code_for_token(code)
        
        # 3. user_data가 있으면 token_response에 추가
        if user_data:
            token_response["user"] = user_data
        
        # 4. 사용자 정보 조회
        user_info = await self.get_user_info(token_response)
        
        return user_info