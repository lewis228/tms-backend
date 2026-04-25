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
    __tablename__ = "user"

    __table_args__ = (
        Index("uq_user_email_active_true", "email", "is_active_true", unique=True),
        Index("uq_user_oauth_active", "auth_provider", "oauth_id", "is_active_true", unique=True),
        Index("ix_user_email", "email"),
        Index("ix_user_auth_provider", "auth_provider"),
    )

    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(
        String(20), default=AuthProviderEnum.EMAIL.value,
        server_default=AuthProviderEnum.EMAIL.value, nullable=False
    )
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[RolesEnum] = mapped_column(SAEnum(RolesEnum), default=RolesEnum.USER, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    notification_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_notification_enabled: Mapped[bool] = mapped_column(default=False, server_default="0", nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, server_default="auto")

    is_active_true: Mapped[Optional[int]] = mapped_column(
        Integer, Computed("CASE WHEN is_active = 1 THEN 1 ELSE NULL END", persisted=False), nullable=True,
    )

    teams = relationship(
        "UserTeamModel", back_populates="user",
        cascade="all, delete-orphan", lazy=settings.ORM_LAZY_DEFAULT,
        order_by="UserTeamModel.id.asc()",
        primaryjoin=lambda: foreign(__import__("team.model", fromlist=["UserTeamModel"]).UserTeamModel.user_id) == UserModel.id,
    )

    files = relationship(
        FileAssetModel, viewonly=True, lazy=settings.ORM_LAZY_DEFAULT,
        order_by="FileAssetModel.id.asc()",
        primaryjoin=lambda: and_(
            FileAssetModel.domain == FileDomain.USER,
            foreign(FileAssetModel.object_id) == UserModel.id,
        ),
    )

    @validates("email")
    def _normalize_email(self, key, value: str) -> str:
        return value.lower() if value else value

    @validates("notification_email")
    def _normalize_notification_email(self, key, value: str) -> str:
        return value.lower() if value else value

    @classmethod
    def create_email_user(cls, *, email: str, password_hash: str, name: str = None) -> "UserModel":
        email_lower = email.lower()
        return cls(
            email=email_lower, password=password_hash,
            auth_provider=AuthProviderEnum.EMAIL.value,
            name=name or email.split("@")[0],
            notification_email=email_lower,
        )

    @classmethod
    def create_oauth_user(cls, *, provider: AuthProviderEnum, oauth_id: str, email: str = None, name: str = None) -> "UserModel":
        email_lower = email.lower() if email else None
        return cls(
            email=email_lower, password=None,
            auth_provider=provider.value, oauth_id=oauth_id,
            name=name, notification_email=email_lower,
        )
