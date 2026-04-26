# rbac/model.py
from __future__ import annotations

from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, UniqueConstraint, Index,
    ForeignKeyConstraint, JSON
)
from sqlalchemy.orm import mapped_column, relationship, Mapped, foreign
from common.model.base_model import Base
from common.model.tenant_scoped_mixin import TenantScopedMixin
from common.const.settings import settings
from tenant.model import UserTenantModel

# ─────────────────────────────────────────────────────────
# 지연 임포트 헬퍼 (순환참조 안전)
# ─────────────────────────────────────────────────────────
def _Team():
    from tenant.model import TenantModel
    return TenantModel

def _UserTenant():
    """순환 회피용 lazy 참조."""
    from tenant.model import UserTenantModel
    return UserTenantModel


# ─────────────────────────────────────────────────────────
# 단일 권한 코드 (글로벌 마스터)
# ─────────────────────────────────────────────────────────
class PermissionModel(Base):
    __tablename__ = "permissions"

    code        = mapped_column(String(64), unique=True, index=True, nullable=False)
    label       = mapped_column(String(100), nullable=False)
    category    = mapped_column(String(50), nullable=True)
    description = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_permissions_category", "category"),
    )

    # Permission ← PermissionGroupPermission (1:N, 역참조)
    groups: Mapped[list["PermissionGroupPermission"]] = relationship(
        "PermissionGroupPermission",
        back_populates="permission",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by=lambda: PermissionGroupPermission.id.asc(),
        # 문자열 foreign_keys 제거, primaryjoin만 유지
        primaryjoin=lambda: foreign(PermissionGroupPermission.permission_id) == PermissionModel.id,
    )


# ─────────────────────────────────────────────────────────
# 권한 그룹 (팀 스코프)
# ─────────────────────────────────────────────────────────
class PermissionGroupModel(Base, TenantScopedMixin):
    __tablename__ = "permission_groups"
    __table_args__ = (
        # 팀 내 시스템키 유니크(ADMIN/MEMBER/VIEWER 보호용)
        UniqueConstraint("tenant_id", "system_key", name="uq_permgroup_system_key"),

        # 팀 스코프 공통 패턴(커서/조인 안정화)
        UniqueConstraint("tenant_id", "id", name="uq_permission_groups_tenant_id_id"),
        Index("ix_permission_groups_tenant_id_id", "tenant_id", "id"),

        # 자주 쓰는 조회/정렬 경로
        Index("ix_permission_groups_tenant_name", "tenant_id", "name"),
        Index("ix_permission_groups_team_is_system", "tenant_id", "is_system"),
        Index("ix_permission_groups_team_updated_at", "tenant_id", "updated_at"),
    )

    name       = mapped_column(String(255), nullable=False)
    is_admin   = mapped_column(Boolean, default=False, nullable=False)
    is_system  = mapped_column(Boolean, default=False, nullable=False)
    system_key = mapped_column(String(20), nullable=True)  # 'ADMIN'|'MEMBER'|'VIEWER'|NULL

    # NEW: 그룹 권한 버전 (코드셋 변경 시 증가)
    version    = mapped_column(Integer, nullable=False, default=1, server_default="1")  # NEW

    # 속성 접근 제외 ID 목록 (JSON: List[int] | None)
    # NULL / [] = 제외 없음(전체 접근), [1,3] = 해당 속성 ID 접근 제외
    excluded_attribute_ids = mapped_column(JSON, nullable=True, default=None)

    # 권한 그룹 → 권한 매핑 (1:N)
    permissions: Mapped[list["PermissionGroupPermission"]] = relationship(
        "PermissionGroupPermission",
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by=lambda: PermissionGroupPermission.id.asc(),
        primaryjoin=lambda: (
            (foreign(PermissionGroupPermission.tenant_id) == PermissionGroupModel.tenant_id) &
            (foreign(PermissionGroupPermission.group_id) == PermissionGroupModel.id)
        ),
        # 문자열 foreign_keys 제거
    )

    # 권한 그룹 → UserTenant (1:N)
    # FK는 user_tenants.permission_group_id (RESTRICT — 멤버십 있으면 그룹 삭제 금지)
    user_tenants: Mapped[list["UserTenantModel"]] = relationship(
        "UserTenantModel",
        back_populates="permission_group",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by=lambda: _UserTenant().id.asc(),
        primaryjoin=lambda: foreign(_UserTenant().permission_group_id) == PermissionGroupModel.id,
    )


# ─────────────────────────────────────────────────────────
# 권한 그룹 ↔ 권한 코드 매핑(Association, 팀 스코프)
# ─────────────────────────────────────────────────────────
class PermissionGroupPermission(Base, TenantScopedMixin):
    __tablename__ = "permission_group_permissions"

    # 조인 테이블이므로 TenantScopedMixin의 tenant 관계를 끈다
    __with_tenant_rel__ = False

    __table_args__ = (
        # (tenant_id, id) 커서/조인 안정화 패턴
        UniqueConstraint("tenant_id", "id", name="uq_pgperm_tenant_id_id"),
        Index("ix_pgperm_tenant_id_id", "tenant_id", "id"),

        # 팀 단위 중복 매핑 방지
        UniqueConstraint("tenant_id", "group_id", "permission_id", name="uq_pgperm_team_group_perm"),

        # 자주 쓰는 조회/집계 경로
        Index("ix_pgperm_team_group", "tenant_id", "group_id"),
        Index("ix_pgperm_team_permission", "tenant_id", "permission_id"),

        # 복합 FK: (tenant_id, group_id) → permission_groups(tenant_id, id)
        ForeignKeyConstraint(
            ["tenant_id", "group_id"],
            ["permission_groups.tenant_id", "permission_groups.id"],
            ondelete="CASCADE",
            name="fk_pgperm_group_tenant_id_id",
        ),
    )

    # group_id는 위 복합 FK 일부
    group_id = mapped_column(Integer, nullable=False, index=True)

    # 권한 FK: 글로벌 마스터
    permission_id = mapped_column(
        Integer, ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # 매핑 → 그룹 (N:1)
    group: Mapped["PermissionGroupModel"] = relationship(
        "PermissionGroupModel",
        back_populates="permissions",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: (
            (foreign(PermissionGroupPermission.tenant_id) == PermissionGroupModel.tenant_id) &
            (foreign(PermissionGroupPermission.group_id) == PermissionGroupModel.id)
        ),
        foreign_keys=(group_id,),   # 여기서는 실제 Column 객체이므로 OK
        passive_deletes=True,
    )

    # 매핑 → 권한 (N:1)
    permission: Mapped["PermissionModel"] = relationship(
        "PermissionModel",
        back_populates="groups",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: foreign(PermissionGroupPermission.permission_id) == PermissionModel.id,
        foreign_keys=[permission_id],  # 실제 Column 객체이므로 OK
        passive_deletes=True,
    )

