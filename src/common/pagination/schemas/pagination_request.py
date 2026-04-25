# common/pagination/schemas/pagination_request.py
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field


class BasePaginationSchema(BaseModel):
    """
    공통 페이지네이션 요청 DTO
    ─────────────────────────────────────────────

     커서 기반 페이지네이션:
    - id 정렬: where__id__more_than / where__id__less_than 사용
    - 다른 필드 정렬: 복합 커서 (cursor__field + cursor__value + cursor__id) 사용

     복합 커서 (Compound Cursor):
    - 정렬 필드가 id가 아닐 때 사용
    - cursor__field: 정렬 필드명 (예: 'biz_date')
    - cursor__value: 정렬 필드의 마지막 값
    - cursor__id: 마지막 아이템의 id (동일 값 처리용)
    - WHERE (field < value) OR (field = value AND id < cursor_id) 조건 생성

     include_total:
    - True: COUNT 쿼리 실행하여 total 반환 (첫 요청 시만)
    - False: COUNT 쿼리 생략 (추가 요청 시)
    """

    # ─────────────────────────────────────────────
    # 공통 파라미터
    # ─────────────────────────────────────────────
    take: int = Field(
        default=20,
        description="한 번에 가져올 최대 개수"
    )

    # ─────────────────────────────────────────────
    # 단순 커서 파라미터 (id 정렬용)
    # ─────────────────────────────────────────────
    where__id__less_than: Optional[int] = Field(
        default=None,
        description="커서: id가 이 값보다 작은 것들 (DESC 정렬 시)"
    )
    where__id__more_than: Optional[int] = Field(
        default=None,
        description="커서: id가 이 값보다 큰 것들 (ASC 정렬 시)"
    )

    # ─────────────────────────────────────────────
    # 복합 커서 파라미터 (다른 필드 정렬용)
    # ─────────────────────────────────────────────
    cursor__id: Optional[int] = Field(
        default=None,
        description="복합 커서: 마지막 아이템의 id"
    )
    cursor__field: Optional[str] = Field(
        default=None,
        description="복합 커서: 정렬 필드명 (예: 'biz_date', 'name')"
    )
    cursor__value: Optional[str] = Field(
        default=None,
        description="복합 커서: 정렬 필드의 마지막 값 (문자열로 전달)"
    )

    # ─────────────────────────────────────────────
    # 정렬 파라미터
    # ─────────────────────────────────────────────
    order__id: Optional[Literal['ASC', 'DESC']] = Field(
        default='ASC',
        description="정렬 방향 (기본: ASC)"
    )

    # ─────────────────────────────────────────────
    # total 조회 옵션
    # ─────────────────────────────────────────────
    include_total: bool = Field(
        default=False,
        description="True면 COUNT 쿼리 실행하여 total 반환"
    )
