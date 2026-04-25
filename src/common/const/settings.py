# common/const/settings.py
"""
환경 설정 (K8s 읽기/쓰기 분리 지원)

.env에는 환경마다 달라지는 값만 둔다.
코드 상수(알고리즘, 쿠키 이름, OTP 정책 등)는 여기서 직접 정의.
"""
from __future__ import annotations

# 부트스트랩을 Settings 인스턴스화 전에 실행해 os.environ을 채운다.
from common.const import config_bootstrap  # noqa: F401

from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
import json


# ═════════════════════════════════════════════════════════════
# 코드 상수 (환경별로 바뀌지 않는 값)
# ═════════════════════════════════════════════════════════════

# JWT
JWT_ALGORITHM = "HS256"
BCRYPT_ROUNDS = 10

# Header 이름
CLIENT_TYPE_HEADER = "X-Client-Type"
DEVICE_KEY_HEADER = "X-Device-Key"

# Cookie 이름
BROWSER_ID_COOKIE_NAME = "browser_id"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"

# OTP 정책
OTP_SEND_LIMIT = 3       # 같은 이메일 발송 허용 횟수
OTP_BLOCK_SEC = 60        # 차단 시간(초)
OTP_MAX_TRIES = 5         # 단일 코드 입력 허용 횟수
OTP_TTL = 180             # 코드 유효시간(초)
OTP_OK_TTL = 900          # 인증성공 후 비밀번호 입력 허용 시간(초)
OTP_GRACE_SEC = 5         # 유예 시간(초)

# MinIO / S3 상수
MINIO_REGION = "us-east-1"
MINIO_TEMP_PREFIX = "tmp"
MINIO_PRESIGNED_UPLOAD_TTL = 86400   # 24시간
MINIO_PRESIGNED_DOWNLOAD_TTL = 86400

# CORS (개발환경 기본: 로컬/사설망 허용)
DEFAULT_CORS_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?$"
)

# OAuth state TTL
OAUTH_STATE_TTL = 600

# 기타
PURGE_GRACE_DAYS = 30
REDIS_SESSION_MAX_AGE = 3600


class Settings(BaseSettings):
    # ===== 환경 =====
    ENV: str
    LOG_LEVEL: str

    # ===== 시크릿 =====
    JWT_SECRET: str
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
    DB_WRITE_HOST: Optional[str] = None
    DB_READ_HOST: Optional[str] = None

    # ===== DB 타임아웃/풀 =====
    DB_READ_TIMEOUT: int = 30
    DB_WRITE_TIMEOUT: int = 600
    DB_MAX_EXEC_MS: int = 30000
    DB_LOCK_WAIT_TIMEOUT: int = 10
    DB_WRITE_POOL_SIZE: int = 10
    DB_WRITE_MAX_OVERFLOW: int = 20
    DB_READ_POOL_SIZE: int = 20
    DB_READ_MAX_OVERFLOW: int = 30

    # ===== ORM 설정 =====
    ORM_LAZY_DEFAULT: str = "raise"

    # ===== Redis (개발용 - 단일) =====
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # ===== Redis (운영용 - 읽기/쓰기 분리) =====
    REDIS_WRITE_HOST: Optional[str] = None
    REDIS_READ_HOST: Optional[str] = None

    # ===== TTL =====
    USER_CACHE_TTL: int = 300
    RBAC_USER_TEAM_TTL: int = 300
    RBAC_GROUP_CODES_TTL: int = 300
    ACCESS_TTL: int = 1800
    REFRESH_TTL: int = 8000

    # ===== CORS =====
    ALLOWED_ORIGINS: List[str] = []
    ALLOWED_ORIGIN_REGEX: Optional[str] = None

    # ===== SMTP =====
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_SENDER: str = ""

    # ===== Branding =====
    APP_NAME: str
    BRAND_LOGO_URL: str = ""
    COMPANY_ADDRESS: str = ""

    # ===== MinIO / S3 =====
    # EC2(AWS S3 + IAM Role) 환경에서는 ENDPOINT/ACCESS/SECRET 빈 문자열.
    MINIO_ENDPOINT: str = ""
    MINIO_PUBLIC_URL: Optional[str] = None
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str

    # ===== Redis TLS =====
    REDIS_SSL: bool = False

    # ===== AWS =====
    AWS_REGION: Optional[str] = None

    # ===== 기타 =====
    ROOT_PATH: str = ""
    TIMEZONE: str = "Asia/Seoul"
    FRONTEND_URL: str

    # ===== OAuth - Google =====
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # ===== OAuth - Kakao =====
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = ""

    # ===== OAuth - Apple =====
    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY: str = ""
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
        if isinstance(v, str):
            return v.replace("\\n", "\n")
        return v

    # ===== AIS (선박 위치 추적) =====
    # 어떤 provider 를 쓸지. "mock" | "marinetraffic". 확장 시 새 값 추가.
    AIS_PROVIDER: str = "mock"
    # MarineTraffic / VesselFinder 등의 API 키. provider 가 mock 이면 무시.
    AIS_API_KEY: str = ""
    # Celery Beat 의 poll_fleet_positions 주기 (분). 너무 짧으면 업체 과금 폭발,
    # 너무 길면 지도 실시간성 떨어짐. 5~15분 권장.
    AIS_POLL_INTERVAL_MINUTES: int = 10

    # ===== 헬퍼 프로퍼티 =====
    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def is_db_read_write_split(self) -> bool:
        return bool(self.DB_WRITE_HOST and self.DB_READ_HOST)

    @property
    def is_redis_read_write_split(self) -> bool:
        return bool(self.REDIS_WRITE_HOST and self.REDIS_READ_HOST)

    @property
    def cors_origin_regex(self) -> str:
        """운영이면 .env 값 사용, 개발이면 기본 로컬 패턴"""
        return self.ALLOWED_ORIGIN_REGEX or DEFAULT_CORS_REGEX

    @property
    def cookie_secure(self) -> bool:
        """운영이면 Secure=True, 개발이면 False"""
        return self.is_production

    @property
    def cookie_samesite(self) -> str:
        """운영이면 none (cross-site), 개발이면 lax"""
        return "none" if self.is_production else "lax"

    @property
    def upload_root(self) -> Path:
        return Path("./uploads")

    @property
    def is_google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    @property
    def is_kakao_oauth_enabled(self) -> bool:
        return bool(self.KAKAO_CLIENT_ID)

    @property
    def is_apple_oauth_enabled(self) -> bool:
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
