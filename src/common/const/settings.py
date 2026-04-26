# common/const/settings.py
"""
환경 설정 (K8s 읽기/쓰기 분리 지원)

개발 환경 (ENV=development):
  - 단일 DB_HOST, REDIS_HOST 사용
  - DB_WRITE_HOST, DB_READ_HOST 등은 무시됨

운영 환경 (ENV=production):
  - DB_WRITE_HOST, DB_READ_HOST로 Primary/Replica 분리
  - REDIS_WRITE_HOST, REDIS_READ_HOST로 Primary/Replica 분리
"""
from __future__ import annotations
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
import json


class Settings(BaseSettings):
    # ===== 환경 =====
    ENV: str
    LOG_LEVEL: str

    # ===== JWT / Bcrypt =====
    JWT_SECRET: str
    ALGORITHM: str
    BCRYPT_ROUNDS: int
    SECRET_KEY: str

    # ===== Server =====
    PROTOCOL: str
    HOST: str
    PORT: int

    # ===== Database (개발용 - 단일) =====
    DB_HOST: str
    DB_PORT: int
    DB_USERNAME: str
    DB_PASSWORD: str
    DB_DATABASE: str

    # ===== Database (운영용 - 읽기/쓰기 분리) =====
    # 설정되어 있으면 읽기/쓰기 분리 모드 활성화
    DB_WRITE_HOST: Optional[str] = None  # mysql-primary.binflow.svc
    DB_READ_HOST: Optional[str] = None   # mysql-read.binflow.svc

    # ===== DB 타임아웃/제한 =====
    DB_READ_TIMEOUT: int
    DB_WRITE_TIMEOUT: int
    DB_MAX_EXEC_MS: int
    DB_LOCK_WAIT_TIMEOUT: int

    # ===== DB 커넥션 풀 =====
    DB_WRITE_POOL_SIZE: int = 10
    DB_WRITE_MAX_OVERFLOW: int = 20
    DB_READ_POOL_SIZE: int = 20
    DB_READ_MAX_OVERFLOW: int = 30

    # ===== ORM 설정 =====
    ORM_LAZY_DEFAULT: str  # selectin | joined | subquery | raise | noload

    # ===== Redis (개발용 - 단일) =====
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: Optional[str] = None

    # ===== Redis (운영용 - 읽기/쓰기 분리) =====
    # 설정되어 있으면 읽기/쓰기 분리 모드 활성화
    REDIS_WRITE_HOST: Optional[str] = None  # redis-primary.binflow.svc
    REDIS_READ_HOST: Optional[str] = None   # redis-read.binflow.svc

    # ===== Redis TTL =====
    USER_CACHE_TTL: int
    RBAC_USER_TENANT_TTL: int
    RBAC_GROUP_CODES_TTL: int
    REDIS_SESSION_MAX_AGE: int

    # ===== Token TTL =====
    ACCESS_TTL: int
    REFRESH_TTL: int

    # ===== Headers =====
    CLIENT_TYPE_HEADER: str
    DEVICE_KEY_HEADER: str

    # ===== Cookies =====
    BROWSER_ID_COOKIE_NAME: str
    REFRESH_TOKEN_COOKIE_NAME: str
    BROWSER_COOKIE_HTTPONLY: bool
    BROWSER_COOKIE_SAMESITE: str
    BROWSER_COOKIE_SECURE: bool
    REFRESH_COOKIE_HTTPONLY: bool
    REFRESH_COOKIE_SAMESITE: str
    REFRESH_COOKIE_SECURE: bool

    # ===== CORS =====
    ALLOWED_ORIGINS: List[str]
    ALLOWED_ORIGIN_REGEX: str

    # ===== OTP =====
    OTP_SEND_LIMIT: int
    OTP_BLOCK_SEC: int
    OTP_MAX_TRIES: int
    OTP_TTL: int
    OTP_OK_TTL: int
    OTP_GRACE_SEC: int

    # ===== SMTP =====
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_SENDER: str

    # ===== Branding =====
    APP_NAME: str
    BRAND_LOGO_URL: str
    BRAND_PRIMARY_COLOR: str
    COMPANY_ADDRESS: str

    # ===== MinIO =====
    MINIO_ENDPOINT: str  # 내부 통신용 (예: http://minio:9000)
    MINIO_PUBLIC_URL: Optional[str] = None  # 외부 접근용 (예: https://www.binflow.io/minio) - 없으면 MINIO_ENDPOINT 사용
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    MINIO_REGION: str
    MINIO_PRESIGNED_UPLOAD_TTL: int
    MINIO_PRESIGNED_DOWNLOAD_TTL: int
    MINIO_TEMP_PREFIX: str

    # ===== 기타 =====
    ROOT_PATH: str = ""  # 리버스 프록시 경로 접두어 (운영: "/api")
    TIMEZONE: str
    PURGE_GRACE_DAYS: int

    # ===== OAuth 공통 =====
    OAUTH_STATE_TTL: int = 600  # state 파라미터 유효 시간 (초)
    FRONTEND_URL: str  # .env 필수 (예: http://localhost:3000)

    # ===== OAuth - Google =====
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # ===== OAuth - Kakao =====
    KAKAO_CLIENT_ID: str = ""  # REST API 키
    KAKAO_CLIENT_SECRET: str = ""  # 선택 (보안 강화 시 사용)
    KAKAO_REDIRECT_URI: str = ""

    # ===== OAuth - Apple =====
    APPLE_CLIENT_ID: str = ""  # Service ID
    APPLE_TEAM_ID: str = ""  # Apple Developer Team ID
    APPLE_KEY_ID: str = ""  # Sign in with Apple Key ID
    APPLE_PRIVATE_KEY: str = ""  # .p8 파일 내용 (PEM 형식, \n 포함)
    APPLE_REDIRECT_URI: str = ""

    # ===== Validators =====
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v

    @field_validator("APPLE_PRIVATE_KEY", mode="before")
    @classmethod
    def parse_apple_private_key(cls, v):
        """Apple private key의 \\n을 실제 줄바꿈으로 변환"""
        if isinstance(v, str):
            return v.replace("\\n", "\n")
        return v

    # ===== 헬퍼 프로퍼티 =====
    @property
    def is_production(self) -> bool:
        """운영 환경인지 확인"""
        return self.ENV == "production"

    @property
    def is_db_read_write_split(self) -> bool:
        """DB 읽기/쓰기 분리 모드인지 확인"""
        return bool(self.DB_WRITE_HOST and self.DB_READ_HOST)

    @property
    def is_redis_read_write_split(self) -> bool:
        """Redis 읽기/쓰기 분리 모드인지 확인"""
        return bool(self.REDIS_WRITE_HOST and self.REDIS_READ_HOST)

    @property
    def upload_root(self) -> Path:
        """업로드 루트 경로 (레거시 호환)"""
        return Path("./uploads")

    # ===== OAuth 헬퍼 =====
    @property
    def is_google_oauth_enabled(self) -> bool:
        """Google OAuth 사용 가능 여부"""
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def is_kakao_oauth_enabled(self) -> bool:
        """Kakao OAuth 사용 가능 여부"""
        return bool(self.KAKAO_CLIENT_ID)

    @property
    def is_apple_oauth_enabled(self) -> bool:
        """Apple OAuth 사용 가능 여부"""
        return bool(
            self.APPLE_CLIENT_ID
            and self.APPLE_TEAM_ID
            and self.APPLE_KEY_ID
            and self.APPLE_PRIVATE_KEY
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()