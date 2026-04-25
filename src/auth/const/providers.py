from enum import StrEnum


class AuthProviderEnum(StrEnum):
    EMAIL = "email"
    GOOGLE = "google"
    KAKAO = "kakao"
    APPLE = "apple"

    @classmethod
    def oauth_providers(cls) -> list["AuthProviderEnum"]:
        return [cls.GOOGLE, cls.KAKAO, cls.APPLE]

    @classmethod
    def is_oauth(cls, provider: "AuthProviderEnum") -> bool:
        return provider in cls.oauth_providers()

    def display_name_ko(self) -> str:
        names = {"email": "이메일", "google": "구글", "kakao": "카카오", "apple": "애플"}
        return names.get(self.value, self.value)
