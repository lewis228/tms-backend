# src/file/model.py
from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, BigInteger, Index, UniqueConstraint, ForeignKey
from sqlalchemy import Enum as SAEnum
from common.model.base_model import Base
from file.const.domains import FileDomain


class FileAssetModel(Base):
    """
    파일 메타데이터(경로 요소만 보관)
    ---------------------------------
     team_id nullable 변경:
    - Product, Partner 등: team_id 있음 → 팀 삭제 시 CASCADE
    - User: team_id=NULL → 플랫폼 전역, User 삭제 시 명시적 삭제
    
    경로 구조:
    - team_id 있음: private/team-{id}/{domain}/{object_id}/...
    - team_id=NULL: private/{domain}/{object_id}/...
    
    삭제 정책:
    - 팀 하드 삭제 시: team_id FK(CASCADE)로 해당 팀 파일만 자동 삭제
    - User 삭제 시: 코드에서 명시적으로 delete_scope() 호출
    """
    __tablename__ = "file_asset"

    #  team_id 직접 정의 (nullable=True)
    # User 도메인은 팀과 무관하므로 NULL 허용
    team_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        index=True,
        nullable=True
    )

    # 폴리모픽 스코프
    domain:    Mapped[FileDomain] = mapped_column(SAEnum(FileDomain, name="file_domain"), nullable=False)
    object_id: Mapped[int]        = mapped_column(Integer, nullable=False, index=True)
    subdir:    Mapped[str]        = mapped_column(String(50), default="", nullable=False)

    # 파일 속성
    filename:      Mapped[str]  = mapped_column(String(255), nullable=False)
    size:          Mapped[int]  = mapped_column(BigInteger, default=0, nullable=False)
    mime:          Mapped[str]  = mapped_column(String(128), default="application/octet-stream", nullable=False)
    is_public:     Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    # 논리 경로(브라우저 접근 기준)
    # 예: "private/team-123/product/45/images/a.jpg" (팀 소속)
    # 예: "private/user/1/profile/photo.jpg" (플랫폼 전역)
    logical_path:  Mapped[str] = mapped_column(String(512), nullable=False, index=True)

    __table_args__ = (
        # 팀 스코프 유니크 (team_id=NULL인 경우도 포함)
        UniqueConstraint("team_id", "id", name="uq_file_asset_team_id_id"),
        # 조회 최적화
        Index("ix_file_asset_team_id_id", "team_id", "id"),
        Index("ix_file_asset_team_domain_obj", "team_id", "domain", "object_id"),
        Index("ix_file_asset_team_subdir", "team_id", "subdir"),
        Index("ix_file_asset_logical_path", "logical_path"),
        #  User 도메인용 인덱스 (team_id=NULL)
        Index("ix_file_asset_domain_obj", "domain", "object_id"),
    )