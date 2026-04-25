from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, BigInteger, Index, UniqueConstraint, ForeignKey
from sqlalchemy import Enum as SAEnum
from common.model.base_model import Base
from file.const.domains import FileDomain


class FileAssetModel(Base):
    __tablename__ = "file_asset"

    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=True)
    domain: Mapped[FileDomain] = mapped_column(SAEnum(FileDomain, name="file_domain"), nullable=False)
    object_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    subdir: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    mime: Mapped[str] = mapped_column(String(128), default="application/octet-stream", nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    logical_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id", name="uq_file_asset_team_id_id"),
        Index("ix_file_asset_team_id_id", "team_id", "id"),
        Index("ix_file_asset_team_domain_obj", "team_id", "domain", "object_id"),
        Index("ix_file_asset_domain_obj", "domain", "object_id"),
    )
