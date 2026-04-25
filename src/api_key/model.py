from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Index, UniqueConstraint
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin


class ApiKeyModel(Base, TeamScopedMixin):
    """팀이 발급하는 프로그래머틱 접근용 개인 API 토큰.

    팀당 여러 키 발급 가능 (dev/staging/prod 등). 각각 이름, 선택적 만료일,
    soft-delete 상태를 가진다. 키 문자열 자체는 평문 저장 (Stripe/Linear 관행).
    생성 직후에만 전체 값을 노출하고 이후 UI 에는 ``prefix`` 만 표시한다.

    삭제 정책: 회수(revoke) 시 ``is_active=False``. 언제 회수됐는지는
    ``updated_at`` 이 자동 기록 (회수 후에는 row 수정을 허용하지 않으므로
    ``updated_at`` 이 회수 시점과 일치한다).
    """

    __tablename__ = "api_keys"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 전체 토큰 ("omniq_<token_urlsafe(32)>"). 인증 요청마다 조회되므로 인덱스 필수.
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    # 키 앞 ~12자 — 목록 UI 에서 "omniq_ab12…" 렌더링용 (비밀 부분 재조회 방지).
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    # NULL = 만료 없음. 매 인증 요청에서 확인.
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ``team`` 관계는 TeamScopedMixin 이 자동 제공.

    __table_args__ = (
        # 키는 전역 unique (어느 팀이든 동일한 키 문자열 금지).
        UniqueConstraint("key", name="uq_api_keys_key"),
        UniqueConstraint("team_id", "id", name="uq_api_keys_team_id_id"),
        Index("ix_api_keys_team_id_id", "team_id", "id"),
        Index("ix_api_keys_team_prefix", "team_id", "prefix"),
        Index("ix_api_keys_prefix", "prefix"),
    )
