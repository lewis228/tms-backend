# src/common/model/base_model.py
from __future__ import annotations
from sqlalchemy.ext.declarative import as_declarative
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, DateTime, Boolean, ForeignKey, func


@as_declarative()
class Base:
    """
    모든 모델의 공통 베이스 클래스
    ---------------------------------
    - id: PK
    - is_active: 소프트 삭제용 플래그
    - created_at / updated_at: 생성/수정 시각
    - created_by_user_id / updated_by_user_id: 생성자·수정자 FK (User)
    ---------------------------------
    삭제 정책:
      - 마스터 데이터(상품, 위치 등)는 is_active=False 로 소프트 삭제
      - FK가 하나라도 존재하면 RESTRICT로 하드 삭제 방지
    """

    __abstract__ = True

    id:                 Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    is_active:          Mapped[bool]       = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at:         Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:         Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=True)


    # 절대 metadata를 재정의하지 말 것
    # @declared_attr
    # def metadata(cls):
    #     return cls.__table__.metadata

    # (선택) 자동 테이블명 규칙
    # @declared_attr
    # def __tablename__(cls):
    #     return cls.__name__.replace("Model", "").lower()
