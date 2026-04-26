# common/pagination/schemas/pagination_response.py
from __future__ import annotations
from typing import Generic, TypeVar, List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class CursorPaginationMeta(BaseModel):
    """
    커서 페이지네이션 메타
    ─────────────────────────────────────────────
    
    - count  : 이번 응답에 포함된 아이템 수 (<= take)
    - hasMore: 이어서 더 조회할 데이터가 있는지
    - cursor : {"after": <마지막 id>} 형태 (정렬/방향에 따라 달라짐)
    - next   : 다음 요청을 그대로 날릴 수 있는 URL
    - total  : 전체 개수 (include_total=True일 때만 반환)
    
     total 사용 시나리오:
    - 첫 요청: include_total=True → total 반환
    - 추가 요청: include_total=False → total=null (COUNT 쿼리 생략)
    - 프론트엔드에서 첫 응답의 total을 캐싱하여 사용
    """
    count: int = Field(..., description="이번 응답의 아이템 수")
    hasMore: bool = Field(..., description="다음 페이지가 있는지 여부")
    cursor: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="커서 정보 (예: {'after': 123, 'op': 'more_than'})"
    )
    next: Optional[str] = Field(
        default=None, 
        description="다음 요청을 보낼 수 있는 절대 URL"
    )
    total: Optional[int] = Field(
        default=None,
        description="전체 개수 (include_total=True일 때만 반환)"
    )

    model_config = ConfigDict(from_attributes=True)


class CursorPaginationResult(BaseModel, Generic[T]):
    """
    커서 기반 페이지네이션 응답
    ─────────────────────────────────────────────
    
    사용처:
    - 무한 스크롤 (제품리스트, 위치리스트 등)
    - 드롭다운 선택
    - 전체 로드 (take=-1)
    
    응답 예시:
    {
        "meta": {
            "count": 200,
            "hasMore": true,
            "cursor": {"after": 200, "op": "more_than"},
            "next": "http://.../products?take=200&where__id__more_than=200",
            "total": 20000  // include_total=True일 때만
        },
        "data": [...]
    }
    """
    meta: CursorPaginationMeta
    data: List[T]
    
    model_config = ConfigDict(from_attributes=True)


class PagePaginationResult(BaseModel, Generic[T]):
    """
    페이지 기반 페이지네이션 응답
    ─────────────────────────────────────────────
    
    ⚠️ 현재는 사용하지 않음!
    - 통합 페이지네이션에서는 CursorPaginationResult만 사용
    - 프론트엔드에서 캐시를 슬라이스하여 페이지 처리
    
    레거시 호환용으로 남겨둠.
    """
    data: List[T]
    total: int
    
    model_config = ConfigDict(from_attributes=True)