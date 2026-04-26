# src/user/model.py
from __future__ import annotations
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship, validates, foreign
from sqlalchemy import String, Integer, Computed, Index, and_

from common.model.base_model import Base
from common.const.settings import settings
from user.const.roles import RolesEnum
from auth.const.providers import AuthProviderEnum
from sqlalchemy import Enum as SAEnum

from file.model import FileAssetModel
from file.const.domains import FileDomain


class UserModel(Base):
    """
    플랫폼 전역 사용자 모델 (팀과 독립적).

    ── 로그인 방식 ──
      * EMAIL: 일반 이메일 + 비밀번호 가입 (password 필수)
      * GOOGLE/KAKAO/APPLE: OAuth 로그인 (password 없음, oauth_id 필수)

    ── Email 유니크 정책 ──
      * 활성: is_active_true=1 → email 중복 금지 (provider 상관없이)
      * 비활성: is_active_true=NULL → UNIQUE 비교 제외 → 중복 허용
      
    ── OAuth 유니크 정책 ──
      * 같은 (auth_provider, oauth_id) 조합은 활성 사용자 중 유일해야 함
    """

    __tablename__ = "user"

    __table_args__ = (
        # 활성 유저만 이메일 유니크 보장 (provider 상관없이 같은 이메일 차단)
        Index("uq_user_email_active_true", "email", "is_active_true", unique=True),

        # OAuth 중복 방지 (같은 provider + oauth_id 조합)
        Index("uq_user_oauth_active", "auth_provider", "oauth_id", "is_active_true", unique=True),

        # 조회 최적화용
        Index("ix_user_email", "email"),
        Index("ix_user_auth_provider", "auth_provider"),
    )

    # ── 인증 정보 ─────────────────────────────────────────────
    #  email: OAuth는 이메일 없을 수 있음 (카카오 등)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    #  password: OAuth는 비밀번호 없음
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # bcrypt 해시
    
    #  로그인 방식 (email, google, kakao, apple)
    auth_provider: Mapped[str] = mapped_column(
        String(20), 
        default=AuthProviderEnum.EMAIL.value,
        server_default=AuthProviderEnum.EMAIL.value,
        nullable=False
    )
    
    #  OAuth 제공자의 고유 사용자 ID (sub claim)
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 플랫폼 전역 관리자(개발/플랫폼용) — 팀 스코프 RBAC과는 별개
    role: Mapped[RolesEnum] = mapped_column(SAEnum(RolesEnum), default=RolesEnum.DISPATCHER, nullable=False)

    # ── 프로필 정보 ─────────────────────────────────────────────
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)   # 사용자 이름
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)   # 전화번호 (나중에 사용)

    # ── 알림 설정 ─────────────────────────────────────────────
    #  알림용 이메일 (로그인 이메일과 다를 수 있음)
    notification_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    #  이벤트 및 혜택 알림 수신 여부
    event_notification_enabled: Mapped[bool] = mapped_column(default=False, server_default="0", nullable=False)

    # ── 언어 설정 ─────────────────────────────────────────────
    #  UI 언어 (auto=브라우저 기본, ko, en, es, fr, pt, id, zh-CN, zh-TW, ja, de)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, server_default="auto")

    # ── 가상 컬럼: 활성 상태만 1, 비활성은 NULL ─────────────────
    # MySQL: GENERATED ALWAYS AS (CASE WHEN is_active = 1 THEN 1 ELSE NULL END)
    # SQLAlchemy: Computed(expr, persisted=False)  → 가상(virtual) 컬럼
    is_active_true: Mapped[Optional[int]] = mapped_column(
        Integer,
        Computed("CASE WHEN is_active = 1 THEN 1 ELSE NULL END", persisted=False),
        nullable=True,
    )

    # ── 관계: User ↔ UserTenant (1:N — N:M 멤버십) ──────────────
    # 한 user 가 여러 tenant 소속 가능. 각 멤버십에 별도 permission_group 매핑.
    tenants = relationship(
        "UserTenantModel",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="UserTenantModel.id.asc()",
        primaryjoin=lambda: foreign(__import__("tenant.model", fromlist=["UserTenantModel"]).UserTenantModel.user_id)
        == UserModel.id,
    )

    # ── 관계: User ↔ FileAsset(폴리모픽, view-only) ─────────────
    files = relationship(
        FileAssetModel,
        viewonly=True,
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="FileAssetModel.id.asc()",
        primaryjoin=lambda: and_(
            FileAssetModel.domain == FileDomain.USER,
            foreign(FileAssetModel.object_id) == UserModel.id,
        ),
    )

    # ── 유틸 ──────────────────────────────────────────────────
    @validates("email")
    def _normalize_email(self, key, value: str) -> str:
        # 이메일은 항상 소문자 저장
        return value.lower() if value else value

    @validates("notification_email")
    def _normalize_notification_email(self, key, value: str) -> str:
        # 알림 이메일도 소문자 저장
        return value.lower() if value else value

    @classmethod
    def create_email_user(cls, *, email: str, password_hash: str, name: str = None) -> "UserModel":
        """이메일+비밀번호 가입 사용자 생성"""
        email_lower = email.lower()
        return cls(
            email=email_lower,
            password=password_hash,
            auth_provider=AuthProviderEnum.EMAIL.value,
            name=name or email.split("@")[0],
            notification_email=email_lower,  # 알림 이메일도 같이 설정
        )

    @classmethod
    def create_oauth_user(
        cls,
        *,
        provider: AuthProviderEnum,
        oauth_id: str,
        email: str = None,
        name: str = None,
    ) -> "UserModel":
        """OAuth 가입 사용자 생성"""
        email_lower = email.lower() if email else None
        return cls(
            email=email_lower,
            password=None,  # OAuth는 비밀번호 없음
            auth_provider=provider.value,
            oauth_id=oauth_id,
            name=name,
            notification_email=email_lower,  #  이메일 있으면 알림 이메일도 설정
        )

    def is_oauth_user(self) -> bool:
        """OAuth 사용자인지 확인"""
        return self.auth_provider != AuthProviderEnum.EMAIL.value

    def is_email_user(self) -> bool:
        """이메일 가입 사용자인지 확인"""
        return self.auth_provider == AuthProviderEnum.EMAIL.value