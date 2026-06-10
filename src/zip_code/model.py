# src/zip_code/model.py
from __future__ import annotations
from sqlalchemy import String, Float, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from common.model.base_model import Base


class ZipCodeModel(Base):
    """미국 우편번호(zip) 전역 마스터 (팀 무관 reference). GeoNames 등 외부 데이터 적재.

    zip 하나 = 한 배달구역(수백~수천 주소). city/state/county 가 zip 의 속성.
    location/customer/terminal 이 zip_id 로 참조 → 정산 dest 자동채움, 존 도시추가 등에 사용.
    """
    __tablename__ = "zip_code"

    zip:    Mapped[str] = mapped_column(String(16), nullable=False)
    city:   Mapped[str] = mapped_column(String(120), nullable=False)
    state:  Mapped[str] = mapped_column(String(8), nullable=False)   # 2글자 약어(CA)
    county: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latitude:  Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("zip", name="uq_zip_code_zip"),
        Index("ix_zip_code_zip", "zip"),
        Index("ix_zip_code_state_city", "state", "city"),
        Index("ix_zip_code_city", "city"),
    )
