# src/common/pagination/CLAUDE.md

⭐ **MANDATORY — 이 프로젝트의 모든 리스트 엔드포인트는 반드시 이 모듈을 통한다.**

---

## 절대 규칙

1. **2개 이상의 행을 반환하는 모든 리스트 엔드포인트는 `CommonService.paginate()`를 사용해야 한다.**
2. **`LIMIT` / `OFFSET` 페이징 금지.**
3. **커서 인코딩/디코딩을 직접 구현하지 말 것** — 반드시 `paginate()` 호출.
4. 단건 조회(`GET /{id}`)와 부모당 아이템이 bounded로 보장되는 서브리소스(예: shipment당 container ≤ 수십 개)는 이 규칙의 예외.

---

## 왜 cursor인가

- Offset 페이징은 깊은 페이지에서 DB가 앞의 N개를 읽고 버려야 해서 O(N) 비용
- Cursor 페이징은 `WHERE id > last_id LIMIT take`로 항상 O(take)
- 이동 중에 새 데이터가 삽입돼도 중복/누락 없음
- `next` URL이 그대로 사용 가능한 완전한 URL로 반환돼서 클라이언트 구현이 단순

---

## 요청 스키마 — `BasePaginationSchema`

모든 페이징 request 스키마는 이걸 상속한다.

```python
class BasePaginationSchema(BaseModel):
    take: int = Field(default=20, description="페이지당 최대 아이템 수")

    # 단순 cursor (id 기준 정렬)
    where__id__less_than: Optional[int] = None    # DESC 페이징
    where__id__more_than: Optional[int] = None    # ASC 페이징

    # 복합 cursor (비-id 필드로 정렬 시)
    cursor__id: Optional[int] = None              # 마지막 아이템의 id
    cursor__field: Optional[str] = None           # 정렬 필드명 (예: "created_at")
    cursor__value: Optional[str] = None           # 정렬 필드의 마지막 값

    # 정렬 방향
    order__id: Optional[Literal["ASC", "DESC"]] = Field(default="ASC")

    # 전체 개수 (첫 요청에서만 COUNT 실행)
    include_total: bool = Field(default=False)
```

도메인 스키마는 이걸 상속해서 필터/정렬 필드를 추가:

```python
# user/schemas/request.py
class PaginateUserRequestSchema(BasePaginationSchema):
    order__email: Optional[Literal["ASC", "DESC"]] = None
    order__created_at: Optional[Literal["ASC", "DESC"]] = None
    where__email__i_like: Optional[str] = None
    where__role__equal: Optional[str] = None
```

---

## 필터 연산자 (`common/const/filter_mapper.py`)

쿼리 스트링에 `where__<field>__<op>=<value>` 형태로 온다.

| 연산자 | SQL | 예시 |
| --- | --- | --- |
| `equal` | `=` | `where__status__equal=tracking` |
| `i_like` | `ILIKE '%v%'` (case-insensitive) | `where__email__i_like=gmail` |
| `like` | `LIKE '%v%'` | |
| `more_than` | `>` | |
| `less_than` | `<` | |
| `more_than_or_equal` | `>=` | |
| `less_than_or_equal` | `<=` | |
| `in` | `IN (...)` | 콤마 구분 또는 리스트 |
| `between` | `BETWEEN a AND b` | `"10,20"` 또는 `[10,20]` |
| `starts_with` | `LIKE 'v%'` | |
| `ends_with` | `LIKE '%v'` | |
| `is_null` | `IS NULL` / `IS NOT NULL` | bool |

**새 연산자가 필요하면 `common/const/filter_mapper.py`만 수정** — paginate 호출부는 손 안 댐.

---

## 응답 스키마 — `CursorPaginationResult[T]`

```python
class CursorPaginationResult(BaseModel, Generic[T]):
    meta: CursorPaginationMeta
    data: List[T]

class CursorPaginationMeta(BaseModel):
    count: int                                   # 이번 응답의 아이템 수 (≤ take)
    hasMore: bool                                # 다음 페이지가 있는지
    cursor: Optional[Dict[str, Any]] = None      # {"after": 200, "op": "more_than"}
    next: Optional[str] = None                   # 다음 요청 URL (완전한 절대 URL)
    total: Optional[int] = None                  # include_total=True일 때만
```

**응답 예시**:
```json
{
  "meta": {
    "count": 20,
    "hasMore": true,
    "cursor": {"after": 200, "op": "more_than"},
    "next": "http://localhost:8080/api/v1/user?take=20&where__id__more_than=200",
    "total": 5000
  },
  "data": [ ... ]
}
```

---

## 사용 패턴 (router → service → repository)

### 1. Router

```python
# user/router.py
from common.pagination.schemas.pagination_response import CursorPaginationResult

@router.get("", response_model=CursorPaginationResult[UserListItemResponseSchema])
async def get_users(
    request: PaginateUserRequestSchema = Depends(),   # 쿼리스트링 자동 파싱
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    db: AsyncSession = Depends(get_read_db),
):
    svc = UserService(db)
    return await svc.list_users_paginated(request)
```

- `Depends()`만 붙이면 FastAPI가 쿼리스트링을 자동으로 스키마 필드로 파싱
- `response_model`은 반드시 `CursorPaginationResult[<YourResponseSchema>]`

### 2. Service

```python
# user/service.py
async def list_users_paginated(
    self, request: PaginateUserRequestSchema,
) -> CursorPaginationResult[UserListItemResponseSchema]:
    result = await self.repo.list_paginated(request)   # repo가 CommonService.paginate 호출
    result.data = [UserListItemResponseSchema.model_validate(u) for u in result.data]
    return result
```

- Repository는 ORM 모델 담긴 결과를 반환 — Service에서 Pydantic 변환
- `result.data`만 교체 / `result.meta`는 그대로

### 3. Repository

```python
# user/repository.py
class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.common = CommonService()

    async def list_paginated(
        self, request: PaginateUserRequestSchema,
    ) -> CursorPaginationResult[UserModel]:
        base = select(UserModel).where(UserModel.is_active.is_(True))
        base = self._with_options_detail(base)   # eager load 옵션
        if request.where__email__i_like:
            q = f"%{request.where__email__i_like.strip().lower()}%"
            base = base.where(func.lower(UserModel.email).like(q))
        return await self.common.paginate(
            request=request,
            model=UserModel,
            session=self.db,
            base_query=base,
            path="user",    # next URL의 path 부분
        )
```

**`base_query`에는 도메인 고유 WHERE/eager load를 미리 적용**. `paginate()`가 거기에 cursor/where__*/order__*/LIMIT를 자동 얹어서 실행한다.

---

## `CommonService.paginate()` 시그니처

```python
async def paginate(
    self,
    request: BasePaginationSchema,
    model: Type,
    session: AsyncSession,
    base_query=None,                                        # Optional[Select]
    path: str = "",                                         # next URL용
    result_extractor: Optional[Callable[[Any], list]] = None,
    id_accessor: Optional[Callable[[Any], int]] = None,
):
```

- `base_query=None`이면 `select(model)`로 시작
- `result_extractor` — 결과가 모델 리스트가 아니라 tuple 등이면 변환 함수 지정
- `id_accessor` — cursor에 쓸 id가 `row.id`가 아닐 때 커스터마이즈

---

## 복합 cursor (비-id 정렬)

예: shipment를 `created_at DESC`로 페이징하려는 경우.

```python
class PaginateShipmentRequestSchema(BasePaginationSchema):
    order__created_at: Optional[Literal["ASC", "DESC"]] = "DESC"
    where__status__equal: Optional[str] = None
    where__carrier__equal: Optional[str] = None
```

`paginate()`가 자동으로 `cursor__id` + `cursor__field="created_at"` + `cursor__value="2024-04-20T..."`를 인코딩해서 `next` URL 생성. 클라이언트는 그냥 `next`를 그대로 요청하면 됨.

---

## Sync Delta

클라이언트가 "마지막 동기화 이후 변경분만" 가져올 때 `CommonService.sync_delta()`를 쓴다.

```python
await self.common.sync_delta(
    model=ShipmentModel,
    session=self.db,
    since=last_sync_at,
    team_id=team_id,
    use_soft_delete=True,       # is_active=False인 행은 deleted_ids로 반환
    reverse_active=False,        # True면 is_active=True만 deleted_ids 취급 (hard-delete 도메인)
)
```

- `SyncResponse[T]` — `{updated: List[T], deleted_ids: List[int], synced_at: datetime}`
- `SyncWithAllIdsResponse[T]` — hard delete 도메인에서 "서버에 존재하는 전체 id 목록" 반환

페이징과는 용도가 다르다 (델타 동기화는 mobile/offline-first 클라이언트용).

---

## 해서는 안 되는 것

```python
# ❌ LIMIT/OFFSET
result = await db.execute(select(UserModel).limit(20).offset(page * 20))

# ❌ 커서 직접 인코딩
cursor_str = base64.b64encode(json.dumps({"id": last_id}).encode())

# ❌ paginate 바이패스
items = await db.execute(select(UserModel).where(UserModel.id > last_id).limit(20))

# ❌ 자체 next URL 생성
next_url = f"{host}/api/v1/users?page={page+1}"
```

전부 `CommonService.paginate()` 한 번의 호출로 대체하라.

---

## 서브리소스 예외 (현재 상태)

부모 리소스당 아이템 수가 bounded라고 간주되는 곳은 현재 비페이징 `List[T]` 반환:
- `GET /api/v1/ocean/shipments/{id}/containers`
- `GET /api/v1/ocean/shipments/{id}/events`
- `GET /api/v1/ocean/shipments/{id}/scrape-logs`

부모당 수백/수천 개로 커질 수 있으면 즉시 페이징으로 전환 대상. 새로운 서브리소스 리스트를 추가할 때는 **bounded 여부부터 판단**하고, 모호하면 페이징을 기본값으로 간다.
