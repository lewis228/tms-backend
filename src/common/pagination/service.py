# common/pagination/service.py
from __future__ import annotations
from typing import Type, Callable, Any, Optional, List
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc, func, or_, and_
from datetime import datetime, timezone

from common.pagination.schemas.pagination_request import BasePaginationSchema
from common.pagination.schemas.pagination_response import (
    CursorPaginationResult,
    CursorPaginationMeta,
)
from common.pagination.schemas.sync_response import (
    SyncMeta,
    SyncResponse,
    SyncWithAllIdsResponse,
)
from common.const.filter_mapper import FILTER_MAPPER
from common.const.settings import settings


class CommonService:
    """
    공통 페이지네이션 서비스
    ─────────────────────────────────────────────

     커서 기반 페이지네이션 통일:
    - 모든 페이지네이션은 커서 기반 (id 기준)
    - 다른 필드 정렬(날짜순 등)은 프론트엔드에서 로컬 정렬

     핵심 원칙:
    - 커서는 항상 id 기준 (ASC/DESC)
    - 프론트엔드에서 로컬 정렬/필터링 적용
    - total은 첫 요청 시만 조회 (include_total=True)

     성능 최적화:
    - include_total=False면 COUNT 쿼리 생략
    - 프론트엔드에서 total 캐싱하여 재사용
    """

    async def paginate(
        self,
        request: BasePaginationSchema,
        model: Type,
        session: AsyncSession,
        base_query=None,
        path: str = "",
        result_extractor: Optional[Callable[[Any], list]] = None,
        id_accessor: Optional[Callable[[Any], int]] = None,
    ):
        """
        공통 엔트리 포인트 - 커서 기반 페이지네이션
        ─────────────────────────────────────────────

        - 모든 요청은 커서 기반으로 처리
        - base_query가 있으면 그걸 기반으로 필터/정렬 추가
        - path는 next URL 생성 시 사용

         커스텀 결과 추출 (튜플 결과 지원):
        - result_extractor: 결과에서 아이템 리스트 추출
          기본값: result.scalars().all() (모델만 반환)
          튜플용: lambda r: r.all() (Row 튜플 반환)
        - id_accessor: 아이템에서 id 추출
          기본값: item.id (모델)
          튜플용: lambda row: row[0].id
        """
        return await self.cursor_paginate(
            request, model, session, base_query, path,
            result_extractor, id_accessor
        )

    async def cursor_paginate(
        self,
        request,
        model,
        session,
        base_query=None,
        path="",
        result_extractor: Optional[Callable[[Any], list]] = None,
        id_accessor: Optional[Callable[[Any], int]] = None,
    ):
        """
        커서 기반 페이지네이션
        ─────────────────────────────────────────────

        규칙:
        - 커서 키는 항상 'id' 칼럼 기준
        - ASC: where__id__more_than = <마지막 id>
        - DESC: where__id__less_than = <마지막 id>

        반환 형식:
        - meta.count: 이번 응답 개수 (<= take)
        - meta.hasMore: 더 있는지 여부
        - meta.cursor: 커서 정보
        - meta.next: 다음 요청 URL
        - meta.total: 전체 개수 (include_total=True일 때만)

         include_total 동작:
        - True: COUNT 쿼리 실행 → total 반환
        - False: COUNT 쿼리 생략 → total=null

         커스텀 결과 추출:
        - result_extractor: 결과에서 아이템 추출 (기본: scalars().all())
        - id_accessor: 아이템에서 id 추출 (기본: item.id)
        """
        # 기본 추출 함수 설정
        if result_extractor is None:
            result_extractor = lambda r: list(r.scalars().all())
        if id_accessor is None:
            id_accessor = lambda item: getattr(item, "id")
        # 1) 시작 쿼리 결정
        query = base_query if base_query is not None else select(model)

        # 2) where__* 필터 반영
        query = self.apply_filters(query, model, request)

        # ─────────────────────────────────────────────
        #  total 계산 (include_total=True일 때만)
        # ─────────────────────────────────────────────
        total = None
        if getattr(request, 'include_total', False):
            # 커서 조건 제외한 필터만 적용해서 COUNT
            count_query = base_query if base_query is not None else select(model)
            count_query = self.apply_filters(count_query, model, request, exclude_cursor=True)
            total = await session.scalar(
                select(func.count()).select_from(count_query.subquery())
            )

        # 3) 정렬 적용
        order_clauses = self.build_order_by_clauses(request, model)
        if not order_clauses:
            # 기본: id ASC
            order_clauses = [asc(getattr(model, "id"))]
        query = query.order_by(*order_clauses)

        # 4) 커서 판별을 위해 take+1 조회 (take=-1이면 전체 로드)
        is_load_all = request.take == -1
        if is_load_all:
            result = await session.execute(query)
            items = result_extractor(result)
            has_more = False
            data = items
        else:
            result = await session.execute(query.limit(request.take + 1))
            items = result_extractor(result)
            has_more = len(items) > request.take
            data = items[:request.take]

        # 5) 데이터 없으면 빈 응답
        if not data:
            return CursorPaginationResult(
                data=[],
                meta=CursorPaginationMeta(
                    count=0,
                    hasMore=False,
                    cursor=None,
                    next=None,
                    total=total,
                ),
            )

        # 6) 마지막 id (커서 기준점)
        last_item = data[-1]
        last_id = id_accessor(last_item)

        # 7) 정렬 방향에 따른 커서 연산자
        order_dir = getattr(request, "order__id", None) or "ASC"
        if str(order_dir).upper() == "DESC":
            op_name = "less_than"
            op_key = "where__id__less_than"
        else:
            op_name = "more_than"
            op_key = "where__id__more_than"

        # 8) meta 구성
        if has_more:
            # next URL 구성
            params = request.model_dump(exclude_none=True)
            params.pop("page", None)
            params.pop("where__id__less_than", None)
            params.pop("where__id__more_than", None)
            params.pop("include_total", None)  # next URL에서는 total 제외
            params["take"] = request.take
            params["order__id"] = str(order_dir).upper()
            params[op_key] = last_id

            base = f"{settings.PROTOCOL}://{settings.HOST}:{settings.PORT}"
            next_url = f"{base}/{path}?{urlencode(params)}" if path else f"{base}?{urlencode(params)}"

            meta = CursorPaginationMeta(
                count=len(data),
                hasMore=True,
                cursor={"after": last_id, "op": op_name},
                next=next_url,
                total=total,
            )
        else:
            meta = CursorPaginationMeta(
                count=len(data),
                hasMore=False,
                cursor=None,
                next=None,
                total=total,
            )

        return CursorPaginationResult(data=data, meta=meta)

    def apply_filters(self, query, model, dto: BasePaginationSchema, exclude_cursor: bool = False):
        """
        where__* 필터를 SQLAlchemy 조건으로 변환
        ─────────────────────────────────────────────

        Args:
            query: SQLAlchemy 쿼리
            model: 모델 클래스
            dto: 요청 DTO
            exclude_cursor: True면 커서 조건(where__id__less_than, where__id__more_than) 제외
                           COUNT 쿼리에서 전체 개수를 정확히 계산하기 위해 사용

        규칙:
        - where__<field>__<op>=<value>
        - field: 모델 컬럼명
        - op: FILTER_MAPPER의 연산자 (equal, i_like, between, in, less_than, more_than 등)

        예시:
        - where__name__i_like=pen → column.ilike('%pen%')
        - where__id__less_than=100 → column < 100
        - where__id__more_than=50 → column > 50
        """
        cursor_keys = {"where__id__less_than", "where__id__more_than"}

        for key, value in dto.model_dump(exclude_none=True).items():
            if key.startswith("where__"):
                # 커서 조건 제외 옵션
                if exclude_cursor and key in cursor_keys:
                    continue

                parts = key.split("__")
                column = getattr(model, parts[1], None)
                if not column:
                    continue

                if len(parts) == 2:
                    query = query.where(column == value)
                elif len(parts) == 3:
                    op = parts[2]
                    func_ = FILTER_MAPPER.get(op)
                    if not func_:
                        raise ValueError(f"정상적인 필터조건이 아닙니다: {op}")
                    query = query.where(func_(column, value))

        #  복합 커서 적용 (exclude_cursor가 아닐 때만)
        if not exclude_cursor:
            query = self.apply_compound_cursor(query, model, dto)

        return query

    def apply_compound_cursor(self, query, model, dto: BasePaginationSchema):
        """
        복합 커서 조건을 SQLAlchemy WHERE 절로 변환
        ─────────────────────────────────────────────

         복합 커서란?
        - 정렬 필드가 id가 아닐 때 (예: biz_date, name) 사용
        - cursor__field + cursor__value + cursor__id 조합

         WHERE 조건 생성:
        - DESC 정렬: (field < value) OR (field = value AND id < cursor_id)
        - ASC 정렬: (field > value) OR (field = value AND id > cursor_id)

        예시 (biz_date DESC):
        - cursor__field=biz_date, cursor__value=2024-01-16, cursor__id=225
        - WHERE (biz_date < '2024-01-16') OR (biz_date = '2024-01-16' AND id < 225)
        """
        cursor_id = getattr(dto, 'cursor__id', None)
        cursor_field = getattr(dto, 'cursor__field', None)
        cursor_value = getattr(dto, 'cursor__value', None)

        # 복합 커서 파라미터가 모두 있어야 적용
        if not (cursor_id and cursor_field and cursor_value):
            return query

        # 정렬 필드 컬럼 가져오기
        column = getattr(model, cursor_field, None)
        if not column:
            return query

        # 정렬 방향 확인 (order__<field> 값)
        order_key = f"order__{cursor_field}"
        order_dir = getattr(dto, order_key, None)
        if order_dir is None:
            # order__<field>가 없으면 request의 다른 order 필드 확인
            for key, value in dto.model_dump(exclude_none=True).items():
                if key == order_key:
                    order_dir = value
                    break

        # 기본값: DESC
        is_desc = str(order_dir).upper() == 'DESC' if order_dir else True

        # 커서 값 타입 변환 (문자열 → 적절한 타입)
        typed_value = self._convert_cursor_value(column, cursor_value)

        # WHERE 조건 생성
        if is_desc:
            # DESC: (field < value) OR (field = value AND id < cursor_id)
            condition = or_(
                column < typed_value,
                and_(column == typed_value, model.id < cursor_id)
            )
        else:
            # ASC: (field > value) OR (field = value AND id > cursor_id)
            condition = or_(
                column > typed_value,
                and_(column == typed_value, model.id > cursor_id)
            )

        return query.where(condition)

    def _convert_cursor_value(self, column, value: str):
        """
        커서 값을 컬럼 타입에 맞게 변환
        ─────────────────────────────────────────────

        cursor__value는 항상 문자열로 전달되므로
        컬럼 타입에 맞게 변환 필요
        """
        try:
            # 컬럼 타입 확인
            col_type = str(column.type).upper()

            if 'INT' in col_type:
                return int(value)
            elif 'FLOAT' in col_type or 'DECIMAL' in col_type or 'NUMERIC' in col_type:
                return float(value)
            elif 'DATETIME' in col_type or 'TIMESTAMP' in col_type:
                # ISO 형식 파싱
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif 'DATE' in col_type:
                return datetime.fromisoformat(value).date()
            elif 'BOOL' in col_type:
                return value.lower() in ('true', '1', 'yes')
            else:
                # 문자열 그대로 반환
                return value
        except (ValueError, TypeError):
            return value

    def build_order_by_clauses(self, request: BasePaginationSchema, model: Type):
        """
        order__* 정렬 조건을 SQLAlchemy order_by 절로 변환
        ─────────────────────────────────────────────

        규칙:
        - order__<field>=ASC|DESC
        - 다중 정렬 지원 (order__id, order__name 등)

         order__id는 항상 마지막 (2차 정렬):
        - 다른 정렬 필드가 있으면 1차 정렬로 사용
        - order__id는 2차 정렬 (동일값 정렬용)
        """
        order_clauses = []
        id_clause = None  # order__id는 따로 저장

        for key, value in request.model_dump(exclude_none=True).items():
            if key.startswith("order__"):
                field = key.replace("order__", "")
                column = getattr(model, field, None)
                if not column:
                    continue
                clause = asc(column) if str(value).upper() == "ASC" else desc(column)

                if field == "id":
                    id_clause = clause  # id는 마지막에 추가
                else:
                    order_clauses.append(clause)

        # order__id는 맨 마지막에 (2차 정렬용)
        if id_clause is not None:
            order_clauses.append(id_clause)

        return order_clauses

    # ═══════════════════════════════════════════════════════════════
    # Delta Sync
    # ═══════════════════════════════════════════════════════════════

    async def sync_delta(
        self,
        model: Type,
        session: AsyncSession,
        since: datetime,
        tenant_id: int,
        base_query=None,
        use_soft_delete: bool = True,
        reverse_active: bool = False,
        extra_conditions: Optional[list] = None,
        result_extractor: Optional[Callable[[Any], list]] = None,
    ):
        """
        Delta sync 공통 헬퍼
        ─────────────────────────────────────────────

        since 이후 변경된 데이터만 조회하여 반환.

         Soft-delete 도메인 (use_soft_delete=True):
        - items: since 이후 수정된 활성 아이템 (is_active=True)
        - deleted_ids: since 이후 soft-delete된 아이템 ID (is_active=False)

         Soft-delete 역전 (reverse_active=True) — 삭제된 목록 뷰용:
        - items: since 이후 soft-delete된 아이템 (is_active=False)
        - deleted_ids: since 이후 복구된 아이템 ID (is_active=True)

         Hard-delete 도메인 (use_soft_delete=False):
        - items: since 이후 수정된 활성 아이템
        - all_ids: 현재 존재하는 모든 활성 아이템 ID

        Args:
            model: SQLAlchemy 모델 클래스
            session: DB 세션
            since: 마지막 sync 시각 (UTC)
            tenant_id: 팀 ID
            base_query: 기본 쿼리 (eager loading options 포함, is_active 필터 미포함)
            use_soft_delete: True=soft-delete 도메인, False=hard-delete 도메인
            reverse_active: True=삭제된 목록 뷰 (is_active 반전), use_soft_delete=True일 때만 유효
            extra_conditions: deleted_ids/all_ids 쿼리에 추가할 조건 (예: is_bundle 필터)
            result_extractor: 결과 추출 함수 (기본: scalars().all())
        """
        sync_time = datetime.now(timezone.utc).isoformat()

        if result_extractor is None:
            result_extractor = lambda r: list(r.scalars().all())

        if use_soft_delete:
            # ─── Soft-delete: 활성 + 비활성 모두 조회 후 분리 ───
            # reverse_active=True: 삭제된 목록 뷰 (items=비활성, deleted_ids=활성)
            items_active = not reverse_active    # 기본 True, 역전 시 False
            removed_active = reverse_active       # 기본 False, 역전 시 True

            items_query = base_query if base_query is not None else select(model)
            items_query = items_query.where(
                model.tenant_id == tenant_id,
                model.updated_at >= since,
                model.is_active.is_(items_active),
            )
            if extra_conditions:
                for cond in extra_conditions:
                    items_query = items_query.where(cond)
            items_query = items_query.order_by(asc(model.id))

            result = await session.execute(items_query)
            items = result_extractor(result)

            # 반대쪽 ID 조회 (기본: soft-delete된 ID / 역전: 복구된 ID)
            deleted_query = (
                select(model.id)
                .where(
                    model.tenant_id == tenant_id,
                    model.updated_at >= since,
                    model.is_active.is_(removed_active),
                )
            )
            if extra_conditions:
                for cond in extra_conditions:
                    deleted_query = deleted_query.where(cond)

            deleted_result = await session.execute(deleted_query)
            deleted_ids = [row[0] for row in deleted_result.all()]

            return SyncResponse(
                meta=SyncMeta(count=len(items), sync_time=sync_time),
                items=items,
                deleted_ids=deleted_ids,
            )
        else:
            # ─── Hard-delete: 변경된 활성 아이템 + 전체 활성 ID ───
            items_query = base_query if base_query is not None else select(model)
            items_query = items_query.where(
                model.tenant_id == tenant_id,
                model.is_active.is_(True),
                model.updated_at >= since,
            )
            if extra_conditions:
                for cond in extra_conditions:
                    items_query = items_query.where(cond)
            items_query = items_query.order_by(asc(model.id))

            result = await session.execute(items_query)
            items = result_extractor(result)

            # 전체 활성 ID 조회 (id만 SELECT → 경량)
            ids_query = (
                select(model.id)
                .where(
                    model.tenant_id == tenant_id,
                    model.is_active.is_(True),
                )
            )
            if extra_conditions:
                for cond in extra_conditions:
                    ids_query = ids_query.where(cond)

            ids_result = await session.execute(ids_query)
            all_ids = [row[0] for row in ids_result.all()]

            return SyncWithAllIdsResponse(
                meta=SyncMeta(count=len(items), sync_time=sync_time),
                items=items,
                all_ids=all_ids,
            )
