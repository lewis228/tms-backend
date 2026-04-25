"""환경 설정 — pydantic-settings 기반.

Phase 1에서 모든 도메인이 필요로 하는 키를 추가한다.
.env 파일은 로컬 전용. EC2에서는 AWS Parameter Store/Secrets Manager 권장.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )

    # ── 환경 ─────────────────────────────────────────────
    app_env: str = "local"
    env: str = "development"
    debug: bool = True
    log_level: str = "DEBUG"
    log_format: str = "console"  # "console" | "json"

    # ── Server ──────────────────────────────────────────
    protocol: str = "http"
    host: str = "localhost"
    port: int = 8080
    app_name: str = "TMS"
    frontend_url: str = "http://localhost:5173"
    cors_allowed_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # ── Secrets ─────────────────────────────────────────
    secret_key: str = "dev-change-me"
    jwt_secret: str = "dev-change-me"
    access_ttl_minutes: int = 60
    refresh_ttl_days: int = 30

    # ── Database ────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 3306
    db_username: str = "root"
    db_password: str = "rootpassword"
    db_database: str = "tms"
    db_write_host: Optional[str] = None
    db_read_host: Optional[str] = None
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_replica_pool_size: int = 20
    db_replica_max_overflow: int = 30

    # ── Redis ───────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_ssl: bool = False
    redis_password: Optional[str] = None

    # ── MinIO/S3 ────────────────────────────────────────
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "tms-app"
    minio_public_url: Optional[str] = None
    aws_region: str = "ap-northeast-2"

    # ── SMTP ────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_sender: str = ""

    # ── Anthropic (AI Intake) ───────────────────────────
    anthropic_api_key: str = ""

    @property
    def database_url(self) -> str:
        host = self.db_write_host or self.db_host
        return (
            f"mysql+aiomysql://{self.db_username}:{self.db_password}"
            f"@{host}:{self.db_port}/{self.db_database}?charset=utf8mb4"
        )

    @property
    def database_replica_url(self) -> str:
        host = self.db_read_host or self.db_host
        return (
            f"mysql+aiomysql://{self.db_username}:{self.db_password}"
            f"@{host}:{self.db_port}/{self.db_database}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        scheme = "rediss" if self.redis_ssl else "redis"
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"{scheme}://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
