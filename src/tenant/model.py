# tenant/model.py — N:M (ste 패턴 그대로). 한 user 가 여러 tenant 소속 가능.
from __future__ import annotations

from sqlalchemy import (
    String, Integer, ForeignKey, UniqueConstraint, DateTime, Boolean, Index, and_,
)
from sqlalchemy.orm import mapped_column, relationship, foreign

from common.const.settings import settings
from common.model.base_model import Base
from file.model import FileAssetModel
from file.const.domains import FileDomain


# ── 지연 임포트 헬퍼 (순환참조 안전) ───────────────────────────
def _User():
    from user.model import UserModel
    return UserModel


def _PermissionGroup():
    from rbac.model import PermissionGroupModel
    return PermissionGroupModel


class TenantModel(Base):
    __tablename__ = "tenants"

    name = mapped_column(String(80), nullable=False)

    # 소프트 삭제 메타
    deactivated_at = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by = mapped_column(Integer, nullable=True)
    purge_at       = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    purge_locked   = mapped_column(Boolean, nullable=False, server_default="0")

    # 온보딩 상태
    onboarding_step1_done = mapped_column(Boolean, nullable=False, server_default="0")
    onboarding_step2_done = mapped_column(Boolean, nullable=False, server_default="0")
    onboarding_step3_done = mapped_column(Boolean, nullable=False, server_default="0")
    onboarding_completed  = mapped_column(Boolean, nullable=False, server_default="0")

    # ── tenant 정보 ────────────────────────────────────
    memo      = mapped_column(String(3000), nullable=True)
    timezone  = mapped_column(String(50), nullable=True, server_default="Asia/Seoul")
    image_url = mapped_column(String(500), nullable=True)

    # 회사 정보
    company_name        = mapped_column(String(120), nullable=True)
    registration_number = mapped_column(String(30), nullable=True)
    address             = mapped_column(String(500), nullable=True)
    representative_name = mapped_column(String(80), nullable=True)
    phone_number        = mapped_column(String(30), nullable=True)

    # 표시 설정
    currency             = mapped_column(String(10), nullable=True)
    decimal_places       = mapped_column(Integer, nullable=False, server_default="2")
    product_info_display = mapped_column(String(30), nullable=True, server_default="all")
    product_info_template = mapped_column(String(500), nullable=True)

    # 엑셀 가져오기
    excel_product_identification = mapped_column(String(30), nullable=True, server_default="sku")

    # 바코드 스캔
    gs1_gtin_enabled = mapped_column(Boolean, nullable=False, server_default="0")

    # ── 관계: Tenant → UserTenant (1:N) ─────────────────────────
    members = relationship(
        "UserTenantModel",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by=lambda: UserTenantModel.id.asc(),
        primaryjoin=lambda: and_(
            foreign(UserTenantModel.tenant_id) == TenantModel.id,
        ),
        foreign_keys="UserTenantModel.tenant_id",
        passive_deletes=True,
    )

    # ── 관계: Tenant ↔ FileAsset(폴리모픽, view-only) ─────────────
    files = relationship(
        FileAssetModel,
        viewonly=True,
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="FileAssetModel.id.asc()",
        primaryjoin=lambda: and_(
            FileAssetModel.domain == FileDomain.TENANT,
            foreign(FileAssetModel.object_id) == TenantModel.id,
        ),
    )


class UserTenantModel(Base):
    """User N:M Tenant — ste 패턴 그대로. 한 user 가 여러 tenant 소속 가능."""
    __tablename__ = "user_tenants"
    __table_args__ = (
        # N:M: (user_id, tenant_id) 조합이 유일. 같은 user 가 같은 tenant 에 두 row X
        UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),
        Index("ix_user_tenants_user_id", "user_id"),
        Index("ix_user_tenants_tenant_id", "tenant_id"),
        Index("ix_user_tenants_permission_group_id", "permission_group_id"),
        Index("ix_user_tenants_tenant_updated_at", "tenant_id", "updated_at"),
    )

    user_id = mapped_column(Integer, ForeignKey("user.id",  ondelete="RESTRICT"), nullable=False)
    tenant_id = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"),  nullable=False)

    permission_group_id = mapped_column(
        Integer, ForeignKey("permission_groups.id", ondelete="RESTRICT"),
        nullable=True
    )

    # ── 관계: UserTenant → Tenant (N:1) ─────────────────────────
    tenant = relationship(
        "TenantModel",
        back_populates="members",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: foreign(UserTenantModel.tenant_id) == TenantModel.id,
        foreign_keys=[tenant_id],
        passive_deletes=True,
    )

    # ── 관계: UserTenant → User (N:1) ───────────────────────────
    user = relationship(
        "UserModel",
        back_populates="tenants",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: foreign(UserTenantModel.user_id) == _User().id,
        foreign_keys=[user_id],
    )

    # ── 관계: UserTenant → PermissionGroup (N:1) ────────────────
    permission_group = relationship(
        "PermissionGroupModel",
        back_populates="user_tenants",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: foreign(UserTenantModel.permission_group_id) == _PermissionGroup().id,
        foreign_keys=[permission_group_id],
    )
