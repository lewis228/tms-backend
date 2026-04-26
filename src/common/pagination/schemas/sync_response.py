# common/pagination/schemas/sync_response.py
from __future__ import annotations
from typing import Generic, TypeVar, List
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class SyncMeta(BaseModel):
    """
    Delta sync 메타데이터
    ─────────────────────────────────────────────

    - count: 변경된 아이템 수
    - sync_time: 다음 sync 요청 시 사용할 서버 UTC 타임스탬프 (ISO 8601)
    """
    count: int = Field(..., description="변경된 아이템 수")
    sync_time: str = Field(..., description="서버 UTC 타임스탬프 (다음 sync 시 since 파라미터로 사용)")

    model_config = ConfigDict(from_attributes=True)


class SyncResponse(BaseModel, Generic[T]):
    """
    Soft-delete 도메인용 Delta sync 응답
    ─────────────────────────────────────────────

    - items: since 이후 생성/수정된 활성 아이템
    - deleted_ids: since 이후 soft-delete된 아이템 ID 목록
    - meta: sync 메타데이터

    사용처: Product, Location, Partner
    """
    meta: SyncMeta
    items: List[T]
    deleted_ids: List[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SyncWithAllIdsResponse(BaseModel, Generic[T]):
    """
    Hard-delete 도메인용 Delta sync 응답
    ─────────────────────────────────────────────

    - items: since 이후 생성/수정된 활성 아이템
    - all_ids: 현재 존재하는 모든 활성 아이템 ID (프론트에서 삭제된 ID를 diff로 계산)
    - meta: sync 메타데이터

    사용처: AttributeDef, PriceTemplate, TaxPolicy, DiscountPolicy, CustomFieldDef
    """
    meta: SyncMeta
    items: List[T]
    all_ids: List[int] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
