# src/auth/oauth/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import secrets
import time

from redis.asyncio import Redis
from auth.const.providers import AuthProviderEnum
from common.const.settings import settings


@dataclass
class OAuthUserInfo:
    """
    OAuth 제공자로부터 받은 사용자 정보.
    
    - provider: OAuth 제공자 (google, kakao, apple)
    - oauth_id: 제공자의 고유 사용자 ID (sub claim)
    - email: 이메일 (없을 수 있음 - 카카오 등)
    - name: 이름 (없을 수 있음)
    - profile_image: 프로필 이미지 URL (없을 수 있음)
    """
    provider: AuthProviderEnum
    oauth_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    profile_image: Optional[str] = None


class OAuthProviderBase(ABC):
    """
    OAuth 제공자 공통 인터페이스.
    
    각 제공자(Google, Kakao, Apple)는 이 클래스를 상속받아 구현합니다.
    """
    
    def __init__(self, redis: Redis):
        self.redis = redis
    
    @property
    @abstractmethod
    def provider(self) -> AuthProviderEnum:
        """OAuth 제공자 식별자"""
        pass
    
    @property
    @abstractmethod
    def authorization_url(self) -> str:
        """OAuth 인증 페이지 URL"""
        pass
    
    @property
    @abstractmethod
    def token_url(self) -> str:
        """액세스 토큰 교환 URL"""
        pass
    
    @property
    @abstractmethod
    def userinfo_url(self) -> str:
        """사용자 정보 조회 URL"""
        pass
    
    @property
    @abstractmethod
    def client_id(self) -> str:
        """클라이언트 ID"""
        pass
    
    @property
    @abstractmethod
    def client_secret(self) -> str:
        """클라이언트 시크릿"""
        pass
    
    @property
    @abstractmethod
    def redirect_uri(self) -> str:
        """콜백 URL"""
        pass
    
    @property
    @abstractmethod
    def scopes(self) -> list[str]:
        """요청할 권한 범위"""
        pass
    
    # ═══════════════════════════════════════════════════════════════
    # State 관리 (CSRF 방지)
    # ═══════════════════════════════════════════════════════════════
    
    async def generate_state(self) -> str:
        """
        OAuth state 파라미터 생성 및 Redis에 저장.
        - CSRF 공격 방지용
        - 일정 시간 후 만료
        """
        state = secrets.token_urlsafe(32)
        key = f"oauth_state:{self.provider.value}:{state}"
        await self.redis.set(key, "1", ex=settings.OAUTH_STATE_TTL)
        return state
    
    async def verify_state(self, state: str) -> bool:
        """
        OAuth state 파라미터 검증.
        - 검증 성공 시 Redis에서 삭제 (일회성)
        """
        key = f"oauth_state:{self.provider.value}:{state}"
        result = await self.redis.get(key)
        if result:
            await self.redis.delete(key)
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════
    # OAuth 플로우
    # ═══════════════════════════════════════════════════════════════
    
    async def get_authorization_url(self) -> tuple[str, str]:
        """
        OAuth 인증 페이지 URL 생성.
        
        Returns:
            (authorization_url, state)
        """
        state = await self.generate_state()
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
        }
        
        # 추가 파라미터 (각 provider별로 오버라이드 가능)
        params.update(self._extra_auth_params())
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.authorization_url}?{query}"
        
        return url, state
    
    def _extra_auth_params(self) -> dict:
        """
        인증 URL에 추가할 파라미터.
        각 provider에서 오버라이드 가능.
        """
        return {}
    
    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> dict:
        """
        인증 코드를 액세스 토큰으로 교환.
        
        Args:
            code: OAuth 인증 코드
            
        Returns:
            토큰 응답 딕셔너리 (access_token, id_token 등)
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, token_response: dict) -> OAuthUserInfo:
        """
        액세스 토큰으로 사용자 정보 조회.
        
        Args:
            token_response: exchange_code_for_token()의 반환값
            
        Returns:
            OAuthUserInfo 객체
        """
        pass
    
    async def authenticate(self, code: str, state: str) -> OAuthUserInfo:
        """
        OAuth 인증 전체 플로우 실행.
        
        Args:
            code: OAuth 인증 코드
            state: CSRF 방지용 state
            
        Returns:
            OAuthUserInfo 객체
            
        Raises:
            ValueError: state 검증 실패
            Exception: 토큰 교환 또는 사용자 정보 조회 실패
        """
        # 1. State 검증
        if not await self.verify_state(state):
            raise ValueError("Invalid or expired state parameter")
        
        # 2. 토큰 교환
        token_response = await self.exchange_code_for_token(code)
        
        # 3. 사용자 정보 조회
        user_info = await self.get_user_info(token_response)
        
        return user_info