from __future__ import annotations
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, DateTime, Boolean, Index, and_
from sqlalchemy.orm import mapped_column, relationship, foreign
from common.const.settings import settings
from common.model.base_model import Base
from file.model import FileAssetModel
from file.const.domains import FileDomain


def _User():
    from user.model import UserModel
    return UserModel

def _PermissionGroup():
    from rbac.model import PermissionGroupModel
    return PermissionGroupModel


class TeamModel(Base):
    __tablename__ = "teams"

    name = mapped_column(String(80), nullable=False)
    # Billing / official contact email. Kept separate from member emails so
    # plan-level notifications (invoice, usage alerts) have a stable target
    # even as members churn. Nullable — only required once a team enables
    # paid plan or API access.
    email = mapped_column(String(255), nullable=True)
    # Plan tier drives rate-limit tier in auth/dependencies/rate_limit.py.
    # Free/basic/pro mapping lives there.
    plan = mapped_column(String(20), nullable=False, server_default="free")
    deactivated_at = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_by = mapped_column(Integer, nullable=True)
    purge_at = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    purge_locked = mapped_column(Boolean, nullable=False, server_default="0")
    memo = mapped_column(String(3000), nullable=True)
    timezone = mapped_column(String(50), nullable=True, server_default="Asia/Seoul")

    members = relationship(
        "UserTeamModel", back_populates="team",
        cascade="all, delete-orphan", lazy=settings.ORM_LAZY_DEFAULT,
        order_by=lambda: UserTeamModel.id.asc(),
        primaryjoin=lambda: and_(foreign(UserTeamModel.team_id) == TeamModel.id),
        foreign_keys="UserTeamModel.team_id", passive_deletes=True,
    )

    files = relationship(
        FileAssetModel, viewonly=True, lazy=settings.ORM_LAZY_DEFAULT,
        order_by="FileAssetModel.id.asc()",
        primaryjoin=lambda: and_(
            FileAssetModel.domain == FileDomain.TEAM,
            foreign(FileAssetModel.object_id) == TeamModel.id,
        ),
    )


class UserTeamModel(Base):
    __tablename__ = "user_teams"
    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_user_team"),
        Index("ix_user_teams_user_id", "user_id"),
        Index("ix_user_teams_team_id", "team_id"),
        Index("ix_user_teams_permission_group_id", "permission_group_id"),
    )

    user_id = mapped_column(Integer, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    team_id = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    permission_group_id = mapped_column(Integer, ForeignKey("permission_groups.id", ondelete="RESTRICT"), nullable=True)

    team = relationship("TeamModel", back_populates="members", lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: foreign(UserTeamModel.team_id) == TeamModel.id, foreign_keys=[team_id], passive_deletes=True)
    user = relationship("UserModel", back_populates="teams", lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: foreign(UserTeamModel.user_id) == _User().id, foreign_keys=[user_id])
    permission_group = relationship("PermissionGroupModel", back_populates="user_teams", lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: foreign(UserTeamModel.permission_group_id) == _PermissionGroup().id, foreign_keys=[permission_group_id])
