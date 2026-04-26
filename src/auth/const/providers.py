# src/auth/const/providers.py
from enum import StrEnum


class AuthProviderEnum(StrEnum):
    """
    로그인/가입 방식 Enum
    
    - EMAIL: 일반 이메일 + 비밀번호 가입
    - GOOGLE: Google OAuth
    - KAKAO: Kakao OAuth
    - APPLE: Apple OAuth
    """
    EMAIL = "email"
    GOOGLE = "google"
    KAKAO = "kakao"
    APPLE = "apple"
    
    @classmethod
    def oauth_providers(cls) -> list["AuthProviderEnum"]:
        """OAuth 방식만 반환"""
        return [cls.GOOGLE, cls.KAKAO, cls.APPLE]
    
    @classmethod
    def is_oauth(cls, provider: "AuthProviderEnum") -> bool:
        """OAuth 방식인지 확인"""
        return provider in cls.oauth_providers()
    
    def display_name_ko(self) -> str:
        """UI 표시용 한글 이름"""
        names = {
            "email": "이메일",
            "google": "구글",
            "kakao": "카카오",
            "apple": "애플",
        }
        return names.get(self.value, self.value)