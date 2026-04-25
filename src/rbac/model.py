from __future__ import annotations
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint, Index, ForeignKeyConstraint, JSON
from sqlalchemy.orm import mapped_column, relationship, Mapped, foreign
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from common.const.settings import settings
from team.model import UserTeamModel


def _UserTeam():
    from team.model import UserTeamModel
    return UserTeamModel


class PermissionModel(Base):
    __tablename__ = "permissions"
    code = mapped_column(String(64), unique=True, index=True, nullable=False)
    label = mapped_column(String(100), nullable=False)
    category = mapped_column(String(50), nullable=True)
    description = mapped_column(String(255), nullable=True)
    __table_args__ = (Index("ix_permissions_category", "category"),)
    groups: Mapped[list["PermissionGroupPermission"]] = relationship(
        "PermissionGroupPermission", back_populates="permission",
        cascade="all, delete-orphan", passive_deletes=True, lazy=settings.ORM_LAZY_DEFAULT,
        order_by=lambda: PermissionGroupPermission.id.asc(),
        primaryjoin=lambda: foreign(PermissionGroupPermission.permission_id) == PermissionModel.id,
    )


class PermissionGroupModel(Base, TeamScopedMixin):
    __tablename__ = "permission_groups"
    __table_args__ = (
        UniqueConstraint("team_id", "system_key", name="uq_permgroup_system_key"),
        UniqueConstraint("team_id", "id", name="uq_permission_groups_team_id_id"),
        Index("ix_permission_groups_team_id_id", "team_id", "id"),
    )
    name = mapped_column(String(255), nullable=False)
    is_admin = mapped_column(Boolean, default=False, nullable=False)
    is_system = mapped_column(Boolean, default=False, nullable=False)
    system_key = mapped_column(String(20), nullable=True)
    version = mapped_column(Integer, nullable=False, default=1, server_default="1")
    excluded_attribute_ids = mapped_column(JSON, nullable=True, default=None)

    permissions: Mapped[list["PermissionGroupPermission"]] = relationship(
        "PermissionGroupPermission", back_populates="group",
        cascade="all, delete-orphan", passive_deletes=True, lazy=settings.ORM_LAZY_DEFAULT,
        order_by=lambda: PermissionGroupPermission.id.asc(),
        primaryjoin=lambda: (
            (foreign(PermissionGroupPermission.team_id) == PermissionGroupModel.team_id) &
            (foreign(PermissionGroupPermission.group_id) == PermissionGroupModel.id)
        ),
    )
    user_teams: Mapped[list["UserTeamModel"]] = relationship(
        "UserTeamModel", back_populates="permission_group", lazy=settings.ORM_LAZY_DEFAULT,
        order_by=lambda: _UserTeam().id.asc(),
        primaryjoin=lambda: foreign(_UserTeam().permission_group_id) == PermissionGroupModel.id,
    )


class PermissionGroupPermission(Base, TeamScopedMixin):
    __tablename__ = "permission_group_permissions"
    __with_team_rel__ = False
    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_pgperm_team_id_id"),
        UniqueConstraint("team_id", "group_id", "permission_id", name="uq_pgperm_team_group_perm"),
        Index("ix_pgperm_team_group", "team_id", "group_id"),
        Index("ix_pgperm_team_permission", "team_id", "permission_id"),
        ForeignKeyConstraint(
            ["team_id", "group_id"], ["permission_groups.team_id", "permission_groups.id"],
            ondelete="CASCADE", name="fk_pgperm_group_team_id_id",
        ),
    )
    group_id = mapped_column(Integer, nullable=False, index=True)
    permission_id = mapped_column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)

    group: Mapped["PermissionGroupModel"] = relationship(
        "PermissionGroupModel", back_populates="permissions", lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: (
            (foreign(PermissionGroupPermission.team_id) == PermissionGroupModel.team_id) &
            (foreign(PermissionGroupPermission.group_id) == PermissionGroupModel.id)
        ),
        foreign_keys=(group_id,), passive_deletes=True,
    )
    permission: Mapped["PermissionModel"] = relationship(
        "PermissionModel", back_populates="groups", lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: foreign(PermissionGroupPermission.permission_id) == PermissionModel.id,
        foreign_keys=[permission_id], passive_deletes=True,
    )
