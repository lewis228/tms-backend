# src/common/pagination/CLAUDE.md

⭐ **MANDATORY — 이 프로젝트의 모든 리스트 엔드포인트는 반드시 이 모듈을 통한다.**

---

## 절대 규칙

1. **2개 이상의 행을 반환하는 모든 리스트 엔드포인트는 `CommonService.paginate()` 를 사용해야 한다.**
2. **`LIMIT` / `OFFSET` 페이징 금지.**
3. **커서 인코딩/디코딩을 직접 구현하지 말 것** — 반드시 `paginate()` 호출.
4. 단건 조회 (`GET /{id}`) 와 부모당 아이템이 bounded 로 보장되는 서브리소스는 이 규칙의 예외.

---

## 왜 cursor 인가

- Offset 페이징은 깊은 페이지에서 DB 가 앞의 N 개를 읽고 버려야 해서 O(N) 비용
- Cursor 페이징은 `WHERE id > last_id LIMIT take` 로 항상 O(take)
- 이동 중에 새 데이터가 삽입돼도 중복/누락 없음
- `next` URL 이 그대로 사용 가능한 완전한 URL 로 반환돼서 클라이언트 구현이 단순

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
# delivery_order/schemas/request.py
class PaginateDeliveryOrderRequest(BasePaginationSchema):
    order__created_at: Optional[Literal["ASC", "DESC"]] = "DESC"
    order__eta: Optional[Literal["ASC", "DESC"]] = None
    where__status__equal: Optional[DeliveryStatus] = None
    where__direction__equal: Optional[ShipmentDirection] = None
    where__customer_id__equal: Optional[int] = None
    where__bl_number__i_like: Optional[str] = None
    include_inactive: bool = Field(default=False)   # is_active=False 도 포함할지
```

`include_inactive` 같은 도메인 specific 플래그는 자유롭게 추가 — repository 가 이걸 보고 `.is_active.is_(True)` 필터를 분기.

---

## 필터 연산자 (`common/const/filter_mapper.py`)

쿼리 스트링에 `where__<field>__<op>=<value>` 형태로 온다.

| 연산자 | SQL | 예시 |
| --- | --- | --- |
| `equal` | `=` | `where__status__equal=DISPATCHED` |
| `i_like` | `ILIKE '%v%'` (case-insensitive) | `where__bl_number__i_like=ABC` |
| `like` | `LIKE '%v%'` | |
| `more_than` | `>` | |
| `less_than` | `<` | |
| `more_than_or_equal` | `>=` | `where__eta__more_than_or_equal=2026-05-12` |
| `less_than_or_equal` | `<=` | |
| `in` | `IN (...)` | 콤마 구분 또는 리스트 |
| `between` | `BETWEEN a AND b` | `"10,20"` 또는 `[10,20]` |
| `starts_with` | `LIKE 'v%'` | |
| `ends_with` | `LIKE '%v'` | |
| `is_null` | `IS NULL` / `IS NOT NULL` | bool |

**새 연산자가 필요하면 `common/const/filter_mapper.py` 만 수정** — paginate 호출부는 손 안 댐.

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
    total: Optional[int] = None                  # include_total=True 일 때만
```

**응답 예시**:
```json
{
  "meta": {
    "count": 20,
    "hasMore": true,
    "cursor": {"after": 200, "op": "more_than"},
    "next": "http://localhost:8080/api/v1/delivery-orders?take=20&where__id__more_than=200",
    "total": 5000
  },
  "data": [ ... ]
}
```

---

## 사용 패턴 (router → service → repository)

### 1. Router

```python
# delivery_order/router.py
from common.pagination.schemas.pagination_response import CursorPaginationResult

@router.get("", response_model=CursorPaginationResult[DeliveryOrderResponseSchema])
async def list_delivery_orders(
    request: PaginateDeliveryOrderRequest = Depends(),   # 쿼리스트링 자동 파싱
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DeliveryOrderService(db, team_id).list_paginated(request)
```

- `Depends()` 만 붙이면 FastAPI 가 쿼리스트링을 자동으로 스키마 필드로 파싱
- `response_model` 은 반드시 `CursorPaginationResult[<YourResponseSchema>]`

### 2. Service

```python
# delivery_order/service.py
async def list_paginated(
    self, request: PaginateDeliveryOrderRequest,
) -> CursorPaginationResult[DeliveryOrderResponseSchema]:
    result = await self.repo.list_paginated(request)
    result.data = [DeliveryOrderResponseSchema.model_validate(do) for do in result.data]
    return result
```

- Repository 는 ORM 모델 담긴 결과를 반환 — Service 에서 Pydantic 변환
- `result.data` 만 교체 / `result.meta` 는 그대로

### 3. Repository

```python
# delivery_order/repository.py
class DeliveryOrderRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: int | None):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def list_paginated(
        self, request: PaginateDeliveryOrderRequest,
    ) -> CursorPaginationResult[DeliveryOrderModel]:
        base = select(DeliveryOrderModel).where(
            DeliveryOrderModel.team_id == self._require_team(),
        )
        if not request.include_inactive:
            base = base.where(DeliveryOrderModel.is_active.is_(True))
        if request.where__bl_number__i_like:
            q = f"%{request.where__bl_number__i_like.strip().lower()}%"
            base = base.where(func.lower(DeliveryOrderModel.bl_number).like(q))
        return await self._common_service.paginate(
            request=request,
            model=DeliveryOrderModel,
            session=self.db,
            base_query=base,
            path="delivery-orders",   # next URL 의 path 부분
        )
```

**`base_query` 에는 도메인 고유 WHERE / eager load 를 미리 적용**. `paginate()` 가 거기에 cursor / where__* / order__* / LIMIT 를 자동 얹어서 실행.

**`team_id` 필터는 Repository 가 직접 추가** — paginate() 가 자동으로 추가하지 않음. ⭐ 잊으면 멀티테넌시 누출.

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

- `base_query=None` 이면 `select(model)` 로 시작
- `result_extractor` — 결과가 모델 리스트가 아니라 tuple 등이면 변환 함수 지정
- `id_accessor` — cursor 에 쓸 id 가 `row.id` 가 아닐 때 커스터마이즈

---

## 복합 cursor (비-id 정렬)

예: D/O 를 `created_at DESC` 로 페이징.

```python
class PaginateDeliveryOrderRequest(BasePaginationSchema):
    order__created_at: Optional[Literal["ASC", "DESC"]] = "DESC"
    where__status__equal: Optional[DeliveryStatus] = None
```

`paginate()` 가 자동으로 `cursor__id` + `cursor__field="created_at"` + `cursor__value="2026-05-12T..."` 를 인코딩해서 `next` URL 생성. 클라이언트는 그냥 `next` 를 그대로 요청하면 됨.

---

## DELETE 응답 표준 — 200 + entity

> **DELETE 는 204 No Content 가 아니라 200 + 삭제된 entity 반환.**

```python
# 표준 패턴
async def delete_x(self, x_id: int, *, updater_user_id: int) -> XResponseSchema:
    obj = await self.repo.get_by_id(x_id)        # is_active=True 필터 통과
    if not obj:
        raise NotFoundException("X")
    obj.is_active = False
    obj.updated_by_user_id = updater_user_id
    await self.db.flush()
    await self.db.refresh(obj)                   # PK SELECT — is_active 필터 무관
    return XResponseSchema.model_validate(obj)   # is_active=False 반영된 entity
```

```python
# 라우터
@router.delete("/{x_id}", response_model=XResponseSchema)
async def delete_x(
    x_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(X_WRITE)),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    return await XService(db, team_id).delete_x(x_id, updater_user_id=int(me.id))
```

**WHY**: 프론트가 `setQueryData` 로 즉시 캐시 패치 가능 (추가 fetch 0회). `is_active=False` 가 명시적으로 들어와 다른 클라이언트의 list 화면에서 즉시 사라지게 표현 가능.

`db.refresh()` 가 PK SELECT 라 일반 read 쿼리의 `is_active=True` 필터 영향 안 받음 — soft-delete 직후에도 안전하게 reload.

**예외**: `POST /auth/logout`, `POST /team/{id}/members/leave` 같은 액션 엔드포인트는 204 유지 가능 (entity 없음).

---

## WebSocket entity 이벤트 — id-only payload

> **모든 도메인 service 의 create / update / delete 끝에서 `publish_entity_event` 호출.**

```python
from common.events.entity_publisher import publish_entity_event

class DeliveryOrderService:
    def __init__(self, db, team_id, redis: Optional[Redis] = None):
        self.redis = redis
        ...

    async def _emit(self, event_type: str, entity, **extra):
        await publish_entity_event(self.redis, self.team_id, event_type, entity, **extra)

    async def create(self, body, *, actor_user_id: int):
        do = await self.repo.create(body.model_dump(), actor_user_id=actor_user_id)
        result = DeliveryOrderResponseSchema.model_validate(do)
        await self._emit("delivery_order.created", result)
        return result
```

### 이벤트 type 컨벤션

`<domain>.<action>` — `created` / `updated` / `deleted` / 도메인별 추가 (예: `delivery_order.status.changed`, `leg.driver.assigned`).

**bulk 작업도 단건 N번 dispatch** — 같은 dispatcher 로 일관 처리.

### Payload shape (id-only)

```json
{
  "type": "delivery_order.created",
  "team_id": 1,
  "timestamp": "2026-05-12T15:30:00Z",
  "payload": {
    "id": 123,
    "team_id": 1
  }
}
```

**클라이언트 처리** (web/mobile 공통):
- `created` → 단건 `GET /<domain>/{id}` + cursor cache `prependTo` + detail `setQueryData`
- `updated` → 단건 `GET /<domain>/{id}` + cursor cache `replaceIn` + detail `setQueryData`
- `deleted` → **GET 0회**. cursor cache 에서 즉시 제거 + detail `removeQueries`

### 라우터 → service 에 redis 주입 필수 (mutation 만)

```python
@router.post("", ...)
async def create_x(
    body: ...,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(X_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),  # ← 추가
    me: UserResponseSchema = Depends(get_current_user),
):
    return await XService(db, team_id, redis=redis).create(body, actor_user_id=int(me.id))
```

GET 라우터는 redis 미주입 OK (publish_entity_event 가 None 이면 noop).

### 모바일 / driver app 이벤트

driver 앱은 자기 leg 만 listen. payload 에 `driver_id` / `leg_id` 같은 추가 키를 함께 발행:

```python
await publish_entity_event(
    self.redis, self.team_id, "leg.driver.assigned",
    leg, driver_id=driver_id,         # ← 추가 컨텍스트
)
```

driver 앱이 `driver_id == me.id` 매칭으로 필터.

### 글로벌 도메인 (team_id 없는)

`carrier`, `vessel`, `location` 같은 글로벌 마스터는 현재 WS broadcast skip. `/sync` 엔드포인트로 catch-up.

---

## Sync delta 엔드포인트 — `GET /<domain>/sync?since=<ts>`

> **변동 가능 도메인은 모두 `/sync` 엔드포인트 노출.**
> WS broadcast 와 완전 동일 shape (`{event, id}` 단건의 events 배열).

### 표준 라우터 패턴

```python
from common.pagination.schemas.sync_response import SyncResponse

@router.get("/sync", response_model=SyncResponse)
async def sync_delivery_orders(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """Delta sync — WS reconnect 후 누락된 변경 catch-up."""
    return await DeliveryOrderService(db, team_id).sync_delta(since)
```

`response_model` 은 generic `[T]` X. 항상 단순 `SyncResponse`.

`/sync` 라우터는 path param 보다 **먼저 정의**해야 함 (`/{do_id}` 가 `sync` 를 ID 로 파싱하는 걸 방지):

```python
@router.get("/sync", ...)            # ← 이게 먼저
async def sync_delivery_orders(...): ...

@router.get("/{do_id}", ...)         # ← 그 다음
async def get_delivery_order(...): ...
```

### Service / Repository

```python
# Repository
async def sync_delta(self, since):
    return await self._common_service.sync_delta(
        model=DeliveryOrderModel,
        session=self.db,
        since=since,
        team_id=self._require_team(),
        event_prefix="delivery_order",   # ← <prefix>.created / .updated / .deleted 생성용
        use_soft_delete=True,
    )

# Service
async def sync_delta(self, since):
    return await self.repo.sync_delta(since)
```

### 응답 shape

```json
{
  "events": [
    {"event": "delivery_order.updated", "id": 50},
    {"event": "delivery_order.created", "id": 1000},
    {"event": "delivery_order.deleted", "id": 100}
  ],
  "all_ids": null,
  "meta": {"count": 3, "sync_time": "2026-05-12T15:35:00Z"}
}
```

- **`events`**: 시간순 변경 이벤트 — WS broadcast 와 동일 shape
- **`all_ids`**: hard-delete 도메인 (use_soft_delete=False) 에서만 채움
- **`meta.sync_time`**: 다음 reconnect 의 `since` 로 사용

### 분류 규칙 (서버 자동)

`since` 이후:
- `is_active=True` & `created_at >= since` → `<prefix>.created`
- `is_active=True` & `created_at < since` & `updated_at >= since` → `<prefix>.updated`
- `is_active=False` & `updated_at >= since` (soft-delete) → `<prefix>.deleted`

---

## 페이징 무관 예외 (의도적)

다음만 list 형태이지만 페이징 미적용:

| 엔드포인트 | 이유 |
| --- | --- |
| `GET /location/batch?ids=...` | 명시적 ID 집합 RPC — 정확히 N 개 반환 |
| `GET /analytics/dashboard` | 집계 응답 (count/group by), entity list 아님 |
| `GET /distance-matrix?...` | 거리 매트릭스 — bounded 결과 |
| `GET /driver/tasks/today` | 오늘 할당 leg — driver 별 평균 < 20개. 페이징 불필요 |

새 list 엔드포인트 만들 때 **무조건 페이징** 이 default — 위 예외에 해당하지 않는 한.

---

## 서브리소스 — 동일 페이징 적용

부모 리소스 아래 서브리소스 list 도 모두 cursor 페이징:

- `GET /delivery-orders/{do_id}/containers` — paginated
- `GET /leg/{leg_id}/stops` — paginated
- `GET /leg/{leg_id}/charges` — paginated

**bounded 가정 폐기**. 사업 성장 시 가정이 깨지면 프론트 캐시 패턴이 분기 → 단일 패턴이 백엔드 / 프론트 모두 단순.

---

## 프론트 동기화 정책 (백엔드 보장 사항)

백엔드는 다음을 보장:

| 상황 | 백엔드 응답 |
| --- | --- |
| 사용자 mutation | `setQueryData` 가능한 full entity |
| WS 정상 운영 | **id-only** payload (`{event, id, team_id, ...extra}`) |
| WS reconnect | `/sync?since=<ts>` → **events 배열** (WS 와 동일 shape) |
| 새로 진입 페이지 | cursor pagination 첫 페이지 |
| 글로벌 마스터 | `/sync` 로 catch-up (WS 없음) |

프론트 (web 또는 mobile) 측 정책:
- 페이지마다 mountBehavior (preserve / reset) 명시
- `refetchOnWindowFocus: false` (WS 가 실시간 동기화 책임)
- 본인 mutation → response entity 로 cursor cache patch (추가 fetch 0회)
- WS event → 단건 GET + cache patch
- WS reconnect → `/sync?since=<last_event_at>` → events 배열 → 같은 dispatcher

driver mobile app:
- 화면 진입 시 first page fetch
- WS 로 `leg.*`, `notification.*` listen
- 백그라운드/잠금화면 → push notification (FCM/APNS) 으로 깨움 → 앱 진입 시 sync

---

## 해서는 안 되는 것

```python
# ❌ LIMIT/OFFSET
result = await db.execute(select(DOModel).limit(20).offset(page * 20))

# ❌ 커서 직접 인코딩
cursor_str = base64.b64encode(json.dumps({"id": last_id}).encode())

# ❌ paginate 바이패스
items = await db.execute(select(DOModel).where(DOModel.id > last_id).limit(20))

# ❌ 자체 next URL 생성
next_url = f"{host}/api/v1/delivery-orders?page={page+1}"

# ❌ team_id 필터 안 한 paginate
return await self._common_service.paginate(
    request=request, model=DOModel, session=self.db,
    base_query=select(DOModel),    # ← team_id 누락 — 멀티테넌시 누출!
    path="delivery-orders",
)
```

전부 `CommonService.paginate()` 한 번의 호출 + `base_query` 안에 `team_id` 필터 명시로 대체하라.

---

## 새 도메인 추가 체크리스트 (paginate 인프라 측)

새 도메인 (예: `vehicle_tracking`) 추가 시:

1. **Schema** — `schemas/request.py` 에 `PaginateVehicleTrackingRequest(BasePaginationSchema)` 정의 (필요 시 도메인 필터 추가)
2. **Repository** — `list_paginated()` + `sync_delta()`
3. **Service** — `list_paginated()`, `sync_delta()`, `_emit()` (mutation 메서드 끝마다 호출)
4. **Router** — `GET /` (cursor) + `GET /sync` + DELETE `response_model=XResponseSchema`
5. **CLAUDE.md** — 도메인 특이 사항만 도메인 폴더 CLAUDE.md 에 추가
