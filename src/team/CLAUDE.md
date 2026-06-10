# src/team/CLAUDE.md

⭐ **표준 도메인 모듈 레퍼런스.** 새 도메인이나 기존 도메인 수정 시 **이 파일의 규약을 그대로 따른다**. 헤더+라인+state machine 도메인은 `src/delivery_order/CLAUDE.md` 도 참조.

이 `team/` 자체는 **팀 루트 모델** (`TeamModel`, `UserTeamModel`) 을 담는 특수 도메인이라 `TeamScopedMixin` 은 안 쓰지만, 라우터/서비스/스키마 규약은 동일하게 적용된다.

---

## 0. 폴더 구조

```
<domain>/
├── __init__.py
├── model.py              # SQLAlchemy — (Base, TeamScopedMixin) 이중 상속이 기본
├── repository.py         # TeamScopedRepoMixin 상속
├── service.py            # __init__(db, team_id)
├── router.py             # _1: None = Depends(access_token) + ...
├── state_machine.py      # (옵션) 상태 전이가 있는 도메인만 — delivery_order, leg, invoice
├── schemas/
│   ├── __init__.py
│   ├── request.py        # RequestSchema 상속
│   └── response.py       # ResponseSchema 상속
├── dependencies/         # (옵션) 도메인 전용 FastAPI deps
└── const/                # (옵션) 도메인 상수 (enum, 권한 코드)
```

---

## 1. Model 규약 — 팀 scoped 기본값

### 1-1. 상속 구조

```python
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin

class CustomerModel(Base, TeamScopedMixin):
    __tablename__ = "customer"
    ...
```

- **`(Base, TeamScopedMixin)` 이중 상속이 기본**
- `TeamScopedMixin` 이 자동 주입:
  - `team_id: Mapped[int]` (`FK → teams.id ondelete=CASCADE`, `index=True`, `nullable=False`)
  - `.team` relationship (`lazy="selectin"`)
- 라인 테이블 (예: `ContainerModel`, `LegStopModel`) 은 `__with_team_rel__ = False` 로 `.team` 관계 제거 — 헤더 통해 접근

### 1-2. 팀 scoped 미상속 예외

다음 경우만 `TeamScopedMixin` 없이 `Base` 만 상속:
- 플랫폼 전역 유저 (`UserModel`)
- 팀 자체 (`TeamModel`)
- 조인 테이블로 team_id 가 의미 다른 경우 (`UserTeamModel` — team_id 도 있지만 user_id 와 동등 FK)
- 마스터 카탈로그 (`PermissionModel`)
- 폴리모픽 (`FileAssetModel` — team_id 는 있으나 `domain` + `object_id` 로 소유 결정)

### 1-3. 컬럼 규약

```python
name: Mapped[str]            = mapped_column(String(80), nullable=False)
email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
status: Mapped[DeliveryStatus] = mapped_column(
    SAEnum(DeliveryStatus, name="delivery_status"),
    default=DeliveryStatus.PLANNING,
    server_default=DeliveryStatus.PLANNING.value,
    nullable=False,
)
amount: Mapped[Decimal]      = mapped_column(Numeric(18, 3), nullable=False, default=0, server_default="0")
memo: Mapped[Optional[str]]  = mapped_column(Text, nullable=True)
```

- SQLAlchemy 2.0 스타일 `Mapped[T] = mapped_column(...)`
- 타입 힌트와 `nullable` 일치 (`Optional[T]` ↔ `nullable=True`)
- **DateTime 은 항상 `DateTime(timezone=True)`** (서버 UTC 고정)
- 금액은 `Numeric(18, 3)`, 수량은 `Numeric(18, 4)` (TMS 관행)
- `server_default` (DB 기본값) vs `default` (Python 기본값) 구분
- **상태값은 `SAEnum(EnumClass, name="...")`** — TMS 관행. enum 이름은 snake_case
- 텍스트 필드는 `Text` (memo / note 등 긴 텍스트). 짧은 식별자 / 코드는 `String(N)`
- 폰번호는 `String(32)` (E.164 + 표시 포맷 여유)

### 1-4. 같은 도메인 내부 라인 — 복합 FK 제약

같은 비즈니스 묶음 안의 라인 테이블 (예: `delivery_order` ↔ `container`, `leg` ↔ `leg_stop`) 은 **반드시 복합 FK** 사용 — 크로스 팀 누출 방지:

```python
__table_args__ = (
    ForeignKeyConstraint(
        ["team_id", "delivery_order_id"],
        ["delivery_order.team_id", "delivery_order.id"],
        ondelete="CASCADE",
        name="fk_container_delivery_order_team_id_id",
    ),
    UniqueConstraint("team_id", "id", name="uq_container_team_id_id"),
    ...
)
```

**단순 FK `delivery_order_id → delivery_order.id` 금지.**

### 1-5. 도메인 간 FK — 단순 FK + ondelete 분기

도메인 간 FK (예: `delivery_order.customer_id` → `customer.id`) 는 단순 FK + ondelete 비즈니스 의미별:

```python
customer_id: Mapped[int] = mapped_column(
    ForeignKey("customer.id", ondelete="RESTRICT"),    # ← customer 삭제 시 D/O 보호
    nullable=False,
)
terminal_id: Mapped[int | None] = mapped_column(
    ForeignKey("terminal.id", ondelete="SET NULL"),    # ← terminal 삭제 시 D/O 의 terminal NULL
    nullable=True,
)
vessel_id: Mapped[int | None] = mapped_column(
    ForeignKey("vessel.id", ondelete="SET NULL"),
    nullable=True,
)
```

| ondelete | 비즈니스 의미 | 예 |
| --- | --- | --- |
| `RESTRICT` | 참조 보호 — 사용 중인 master 는 삭제 불가 | customer 가 D/O 에 사용 중이면 삭제 거부 |
| `SET NULL` | 삭제되어도 OK, 참조만 끊김 | terminal / vessel 같은 부가 정보 |
| `CASCADE` | 부모 삭제 시 자식 정리 (같은 도메인 안 라인) | container / leg_stop |

### 1-6. UniqueConstraint(team_id, id) 필수

```python
UniqueConstraint("team_id", "id", name="uq_<table>_team_id_id"),
```

- 복합 FK 의 **타겟** 이 되려면 `(team_id, id)` 가 unique 여야 함 (MySQL 제약)
- 도메인 유니크가 있다면 함께 선언: `UniqueConstraint("team_id", "code", name="uq_customer_team_code")`

### 1-7. 인덱스 — team_id leftmost

```python
Index("ix_<table>_team_id_id",     "team_id", "id"),
Index("ix_<table>_team_status",    "team_id", "status"),
Index("ix_<table>_team_active_id", "team_id", "is_active", "id"),
Index("ix_<table>_team_updated_at","team_id", "updated_at"),
```

**모든 복합 인덱스는 `team_id` 가 첫 컬럼**. 팀 scoped 쿼리 (`WHERE team_id = ? ...`) 의 leftmost prefix 로 B-tree 효율 극대화.

### 1-8. Soft-Delete 정책 (통일)

- **모든 도메인 삭제는 `is_active=False`** — 별도 `deleted_at`/`revoked_at` 컬럼 추가 금지
- "언제 삭제됐는지" 는 `updated_at` (Base 가 `onupdate=func.now()` 자동 관리) 이 담당
- 삭제된 row 의 수정을 서비스 레벨에서 차단하면 `updated_at` ≈ 삭제 시점
- 팀/부모 삭제 시 자식 자동 정리는 DB FK `ondelete=CASCADE` 가 처리 (애플리케이션 코드 불필요)
- 예외: append-only 도메인 (`chassis_event`, `location_ping`) 은 삭제 없음

### 1-9. Relationship — primaryjoin 에 team_id 포함

#### 헤더 → 라인 (1:N, cascade 소유)

```python
containers = relationship(
    "ContainerModel",
    back_populates="delivery_order",
    cascade="all, delete-orphan",
    lazy=settings.ORM_LAZY_DEFAULT,           # "raise"
    order_by="ContainerModel.id.asc()",
    primaryjoin=lambda: and_(
        foreign(ContainerModel.team_id) == DeliveryOrderModel.team_id,
        foreign(ContainerModel.delivery_order_id) == DeliveryOrderModel.id,
    ),
    passive_deletes=True,
)
```

#### 라인 → 헤더 (N:1)

```python
delivery_order = relationship(
    "DeliveryOrderModel",
    back_populates="containers",
    lazy=settings.ORM_LAZY_DEFAULT,
    primaryjoin=lambda: and_(
        foreign(ContainerModel.team_id) == DeliveryOrderModel.team_id,
        foreign(ContainerModel.delivery_order_id) == DeliveryOrderModel.id,
    ),
)
```

#### 도메인 간 FK 의 relationship (단순 FK)

```python
# delivery_order.model
customer = relationship(
    "CustomerModel",
    foreign_keys="DeliveryOrderModel.customer_id",
    lazy=settings.ORM_LAZY_DEFAULT,
)
```

복합 FK 가 아니므로 `primaryjoin` 명시 불필요. `foreign_keys` 만 명시.

#### 폴리모픽 파일 (discriminator)

```python
files: Mapped[list[FileAssetModel]] = relationship(
    "FileAssetModel",
    primaryjoin=lambda: and_(
        foreign(FileAssetModel.team_id) == DeliveryOrderModel.team_id,
        FileAssetModel.domain == FileDomain.DELIVERY_ORDER,
        foreign(FileAssetModel.object_id) == DeliveryOrderModel.id,
    ),
    viewonly=True,
    lazy=settings.ORM_LAZY_DEFAULT,
)
```

#### `updated_by` 관계 (Base 의 FK 컬럼에 관계만 추가)

```python
updated_by: Mapped[Optional[UserModel]] = relationship(
    "UserModel",
    foreign_keys="DeliveryOrderModel.updated_by_user_id",
    lazy="raise",
)
```

### 1-10. 순환 참조 회피

`DeliveryOrderModel` 이 `ContainerModel` 을 참조하고 `ContainerModel` 도 `DeliveryOrderModel` 을 참조하는 경우, Python import 순환을 피하려면 `primaryjoin=lambda: ...` 안에서 **지연 import** 사용:

```python
def _Container():
    from container.model import ContainerModel
    return ContainerModel

containers = relationship(
    "ContainerModel",
    primaryjoin=lambda: and_(
        foreign(_Container().team_id) == DeliveryOrderModel.team_id,
        foreign(_Container().delivery_order_id) == DeliveryOrderModel.id,
    ),
    ...
)
```

---

## 2. Router 규약

### 2-1. APIRouter 설정

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/<domain>", tags=["<domain>"])
```

`main.py` 에서 `app.include_router(team_router)` — prefix/tag 추가 금지.

### 2-2. 엔드포인트 규약

```python
@router.post("", response_model=TeamResponseSchema, status_code=201)
@router.get("/{team_id}", response_model=TeamResponseSchema)
@router.patch("/{team_id}", response_model=TeamResponseSchema)
@router.delete("/{team_id}/members/{user_id}", status_code=204)
```

- **`response_model=` 항상** (예외 없음)
- POST → `status_code=201`, DELETE → `status_code=204` 또는 200 (DELETE+entity 패턴), 나머지 암묵 200
- `summary` / `description` / `responses` 대신 함수 docstring
- path param 은 리소스명 포함 (`/{do_id}`, `/{leg_id}`, 단순 `/{id}` 금지)

### 2-3. Depends 주입 순서 (TMS 패턴)

팀 scoped 엔드포인트의 canonical 순서:

```python
@router.patch("/{do_id}", response_model=DOResponseSchema)
async def update_do(
    do_id: int,                                              # 1. path params
    body: UpdateDORequest,                                   # 2. body
    _1: None = Depends(access_token),                        # 3. JWT 인증 (sentinel)
    _2: None = Depends(permission_guard(DO_WRITE)),          # 4. 권한 체크 (sentinel)
    team_id: int = Depends(get_team_scope),                  # 5. 팀 스코프 ⭐
    db: AsyncSession = Depends(get_write_db),                # 6. DB
    redis: Redis = Depends(get_write_redis),                 # 7. Redis (mutation + WS event 발행)
    me: UserResponseSchema = Depends(get_current_user),      # 8. 현재 유저
):
    return await DeliveryOrderService(db, team_id, redis=redis).update(
        do_id, body, actor_user_id=int(me.id),
    )
```

**순서 고정**: path → body → `access_token` → `permission_guard(...)` → `get_team_scope` → `get_{read|write}_db` → `get_{read|write}_redis` (mutation 만) → `get_current_user`.

> ⚠️ **STE 와 다른 점**: ste 는 `auth: AuthResult = Depends(jwt_or_api_key)` + `_rl: None = Depends(rate_limit)`. tms 는 `_1: Depends(access_token)` + `_2: Depends(permission_guard(...))` 두 개 분리. `rate_limit` 미사용.

- `_1` / `_2` sentinel 변수 — dependency 가 raise 만 하면 됨. 결과 객체 안 받음
- `permission_guard` 는 mutation 에 항상 부착 (read 라우터는 옵션)
- `get_current_user` 는 actor_user_id 필요한 메서드만 (감사 필드 / 권한 결정)
- `get_write_redis` 는 WS event 발행 필요한 mutation 만
- path 에 team_id 가 있는 경우 (`/team/{team_id}/api-keys`) path 의 team_id 와 `get_team_scope` 결과가 일치하는지 라우터에서 검증 (URL 탬퍼링 방어)

### 2-4. DB 세션

| 작업 | Dependency |
| --- | --- |
| GET | `get_read_db` |
| POST / PATCH / DELETE | `get_write_db` |

**100% 엄격.** Service / Repository 는 `commit()` 호출 금지.

### 2-5. 서비스 인스턴스화

```python
svc = DeliveryOrderService(db, team_id, redis=redis)
return await svc.update(do_id, body, actor_user_id=int(me.id))
```

- 라우터 내부 인라인 — DI 프레임워크 안 씀
- **`(db, team_id, redis=...)` 위치 인자** — redis 만 키워드
- 서비스 메서드에 team_id 를 다시 넣지 않음 — 생성자가 이미 바인딩
- `actor_user_id=int(me.id)` — me.id 가 str 일 수도 있어 명시적 캐스팅

### 2-6. 반환 / 예외

- 라우터에서 `model_validate` 호출 금지 — 서비스가 Pydantic 반환
- `try/except` 최소 — `AppException` 전역 핸들러로 전파
- 외부 시스템 (Celery / Redis / OAuth redirect / external API) 정리가 필요할 때만 라우터 try/except

### 2-7. 페이징

```python
@router.get("", response_model=CursorPaginationResult[DOResponseSchema])
async def list_dos(
    request: PaginateDORequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DeliveryOrderService(db, team_id).list_paginated(request)
```

세부: `src/common/pagination/CLAUDE.md`.

### 2-8. /sync 엔드포인트 (path param 보다 먼저)

```python
@router.get("/sync", response_model=SyncResponse)              # ← 먼저
async def sync_dos(since: str, ...): ...

@router.get("/{do_id}", response_model=DOResponseSchema)        # ← 나중
async def get_do(do_id: int, ...): ...
```

`/sync` 가 path param `{do_id}` 에 잡히지 않게 라우터 정의 순서 주의.

---

## 3. Service 규약

### 3-1. 클래스 구조

```python
class DeliveryOrderService:
    def __init__(
        self,
        db: AsyncSession,
        team_id: int,
        redis: Optional[Redis] = None,    # WS event 발행 필요한 mutation 시
    ):
        self.db = db
        self.team_id = team_id
        self.redis = redis
        self.repo = DeliveryOrderRepository(db, team_id)
        # 교차 도메인은 Repository 직접 주입 (Service 직접 호출 금지)
        self.container_repo = ContainerRepository(db, team_id)
        self.customer_repo = CustomerRepository(db, team_id)
```

- **반드시 클래스**. 모듈 레벨 함수 금지
- `__init__(self, db, team_id, redis=None)` 시그니처 — redis 는 옵셔널
- 메서드마다 team_id 받지 않음 — 생성자가 이미 바인딩
- Primary repo 는 `self.repo` 로 고정
- 교차 도메인 repo 는 `self.<other>_repo` 네이밍

### 3-2. 교차 도메인 호출

- **Service → Service 직접 호출 금지** (순환 의존성 + 트랜잭션 경계 모호)
- 다른 도메인 필요 시 Repository 를 직접 주입
- 예외: 저장소 유틸 성격의 서비스 (예: `FileService`, `NotificationService.dispatch`) 는 허용

### 3-3. 메서드 네이밍

| 동사 | 의미 | 반환 |
| --- | --- | --- |
| `create` / `create_*` | INSERT | Pydantic schema |
| `get` / `get_*_by_*` | 단건, 없으면 `NotFoundException` | Pydantic schema |
| `get_*_detail` | 관계 eager load 포함 | Pydantic schema |
| `list_*` / `list_paginated` | 컬렉션 | `List[Schema]` / `CursorPaginationResult[Schema]` |
| `update` / `update_*` | PATCH | Pydantic schema |
| `delete` / `delete_*` | Soft delete (`is_active=False`) + return entity | Pydantic schema |
| `transition` / `<verb>_<state>` | state machine 전이 (예: `dispatch`, `complete`) | Pydantic schema |
| `bulk_*` | bulk 작업 | bulk response schema |
| `sync_delta` / `sync_<x>` | /sync 엔드포인트 | `SyncResponse` |

**`find_*` 금지** — 전부 `get_*` / `list_*`.

### 3-4. 트랜잭션

- **`await self.db.commit()` 절대 호출 금지**
- `await self.db.flush()` + 필요 시 `await self.db.refresh(obj)`
- 예외는 `get_write_db` dependency 가 rollback 처리

예외적 이중 commit (Celery send_task 전) 패턴은 `src/delivery_order/CLAUDE.md` 참고.

### 3-5. 예외 raise

```python
from common.exceptions.base import (
    AppException, NotFoundException, ConflictException,
    ForbiddenException, BadRequestException,
)

raise NotFoundException("DeliveryOrder")
raise ConflictException("이미 디스패치된 D/O 입니다.")

# 커스텀 코드 필요 시 인라인
raise AppException(
    code="DO_ALREADY_DISPATCHED",
    message="이미 디스패치된 D/O 는 변경할 수 없습니다.",
    status_code=status.HTTP_409_CONFLICT,
)
```

도메인 전용 예외 파일 분리 금지 — 인라인 `AppException(code=...)` 권장.

**예외**: state machine 의 전이 위반은 `state_machine.py` 안에 전용 서브클래스 OK (`InvalidStateTransitionError` 등).

### 3-6. Ownership 검사

- **Repository 의 `team_id` 필터가 기본 방어선** — 서비스 레이어에서 `if obj.team_id != self.team_id` 같은 검사는 **불필요** (리포가 이미 처리)
- 단, 리소스 소유 관계를 검증해야 할 때 (예: "이 D/O 의 container 인가") 는 추가 검사 필요
- driver 본인 leg 인지 검증 (driver_mobile) 은 추가 검사 필수: `if leg.assigned_driver_id != me.id: raise Forbidden`

### 3-7. 감사 필드

`created_by_user_id` / `updated_by_user_id` 는 **서비스에서 수동 설정** (또는 repository 의 create 가 받음):

```python
do = await self.repo.create(
    body.model_dump(exclude_unset=True),
    actor_user_id=actor_user_id,
)

# Update 시:
async def update(self, do_id, body, *, actor_user_id):
    obj = await self.repo.get(do_id)
    if not obj: raise NotFoundException("DeliveryOrder")
    payload = body.model_dump(exclude_unset=True)
    for k, v in payload.items():
        setattr(obj, k, v)
    obj.updated_by_user_id = actor_user_id
    await self.db.flush()
    await self.db.refresh(obj)
    return DOResponseSchema.model_validate(obj)
```

`team_id` 는 리포가 자동 세팅하므로 Model 생성 시 생략 가능.

### 3-8. WebSocket entity event (mutation 끝)

```python
async def create(self, body, *, actor_user_id):
    do = await self.repo.create(body.model_dump(exclude_unset=True), actor_user_id=actor_user_id)
    result = DOResponseSchema.model_validate(do)
    await self._emit("delivery_order.created", result)
    return result

async def _emit(self, event_type: str, entity, **extra):
    if self.redis:
        await publish_entity_event(self.redis, self.team_id, event_type, entity, **extra)
```

세부: `src/common/pagination/CLAUDE.md` §"WebSocket entity 이벤트".

---

## 4. Repository 규약

**모든 규약은 `src/common/repository/CLAUDE.md` 참조** — 여기서는 요점만:

1. `TeamScopedRepoMixin` 상속
2. `__init__(self, db: AsyncSession, team_id: Optional[int])` + `super().__init__(team_id)`
3. 모든 쿼리에 `Model.team_id == self._require_team()` 첫 조건
4. Soft-delete 필터 `.is_active.is_(True)` 명시 (또는 `include_inactive` 플래그 분기)
5. `selectinload` (eager load), `joinedload` 금지
6. `create()` 내부에서 `payload["team_id"] = self._require_team()` 세팅
7. `commit()` 호출 없음

---

## 5. Schema 규약

### 5-1. 파일 구조

```
schemas/
├── __init__.py     # from .request import *; from .response import *
├── request.py
└── response.py
```

대규모 도메인도 이 2분할 유지 (verb 별 파일 분리 금지). 단 schema 가 너무 많으면 같은 파일 안에서 섹션 주석으로 분리.

### 5-2. 베이스 클래스

```python
from common.schemas.base import RequestSchema, ResponseSchema

class DeliveryOrderCreateRequest(RequestSchema):
    direction: ShipmentDirection
    customer_id: int
    bl_number: Optional[str] = Field(None, max_length=64)
    booking_number: Optional[str] = Field(None, max_length=64)

class DeliveryOrderResponseSchema(ResponseSchema):
    id: int
    status: DeliveryStatus
    direction: ShipmentDirection
    customer_id: int
    bl_number: Optional[str] = None
    booking_number: Optional[str] = None
    eta: Optional[datetime] = None
    bl_released: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
```

- **`RequestSchema`** → `extra="forbid"`, `alias_generator=to_camel`, `populate_by_name=True`, `str_strip_whitespace=True`
- **`ResponseSchema`** → `from_attributes=True`, `extra="ignore"`, datetime 자동 UTC+Z 직렬화

### 5-3. 네이밍 — 엄격

| 접미사 | 용도 | 예 |
| --- | --- | --- |
| `<Verb><Resource>Request` | 요청 바디 | `DeliveryOrderCreateRequest`, `DeliveryOrderUpdateRequest` |
| `Paginate<Resource>Request` | 페이징 쿼리 | `PaginateDeliveryOrderRequest` |
| `<Resource>ResponseSchema` | 단건 응답 | `DeliveryOrderResponseSchema` |
| `<Resource>ListItemResponseSchema` | 목록 아이템 (상세와 다를 때) | `LegListItemResponseSchema` |
| `<Resource>DetailResponseSchema` | 관계 포함 상세 | `DeliveryOrderDetailResponseSchema` |
| `<Resource>BulkXxxRequest` | bulk 요청 | `DeliveryOrderBulkCreateRequest` |
| `<Resource>BulkXxxResponseSchema` | bulk 응답 | `DeliveryOrderBulkCreateResponseSchema` |
| `<Resource>TransitionRequest` | state 전이 요청 | `DeliveryOrderTransitionRequest` |

> ⚠️ **TMS specific**: ste 는 `Schema` 접미사를 모든 클래스에. tms 는 Request 는 접미사 생략 (`...Request`), Response 는 `...ResponseSchema` 유지. `delivery_order/schemas/request.py` 실제 코드 따름.

### 5-4. Update 스키마

```python
class DeliveryOrderUpdateRequest(RequestSchema):
    bl_number: Optional[str] = Field(None, max_length=64)
    booking_number: Optional[str] = Field(None, max_length=64)
    customer_id: Optional[int] = None
    terminal_id: Optional[int] = None
    eta: Optional[datetime] = None
    bl_released: Optional[bool] = None
    internal_note: Optional[str] = None
```

- 모든 필드 `Optional[...] = None`
- 서비스에서 `body.model_dump(exclude_unset=True)` 로 제공 필드만 적용

### 5-5. Transition 스키마 (state machine 도메인)

```python
class DeliveryOrderTransitionRequest(RequestSchema):
    target: DeliveryStatus
    force: bool = False                  # 관리자 권한 점프 (state machine bypass)
    reason: Optional[str] = None
```

### 5-6. 페이징 요청

```python
from common.pagination.schemas.pagination_request import BasePaginationSchema

class PaginateDeliveryOrderRequest(BasePaginationSchema):
    order__created_at: Optional[Literal["ASC", "DESC"]] = "DESC"
    order__eta: Optional[Literal["ASC", "DESC"]] = None
    where__status__equal: Optional[DeliveryStatus] = None
    where__direction__equal: Optional[ShipmentDirection] = None
    where__customer_id__equal: Optional[int] = None
    where__bl_number__i_like: Optional[str] = None
    include_inactive: bool = Field(default=False)
```

**`BasePaginationSchema` 상속 필수**. 세부: `src/common/pagination/CLAUDE.md`.

### 5-7. Bulk 스키마

```python
class DeliveryOrderBulkCreateRequest(RequestSchema):
    items: List[DeliveryOrderCreateRequest]

class DeliveryOrderBulkUpdateRequest(RequestSchema):
    items: List[DeliveryOrderBulkUpdateItem]

class DeliveryOrderBulkDeleteRequest(RequestSchema):
    ids: List[int]

class DeliveryOrderBulkCreateResponseSchema(ResponseSchema):
    created: List[DeliveryOrderResponseSchema]
    failed: List[BulkFailureItem] = []   # 부분 실패 시
```

---

## 6. State Machine 분리 — 별도 파일

상태 전이가 있는 도메인은 `<domain>/state_machine.py` 별도 파일 권장:

```python
# delivery_order/state_machine.py
from dataclasses import dataclass
from common.exceptions.base import AppException
from delivery_order.const.status import DeliveryStatus
from delivery_order.model import DeliveryOrderModel
from leg.model import LegModel


class InvalidStateTransitionError(AppException):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            code="ERR_INVALID_STATE_TRANSITION",
            message=message, status_code=422, detail=details,
        )


@dataclass
class TransitionContext:
    do: DeliveryOrderModel
    legs: list[LegModel]


_ALLOWED: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.PLANNING:       {DeliveryStatus.DISPATCHED},
    DeliveryStatus.DISPATCHED:     {DeliveryStatus.YARD_STAGED, ...},
    ...
}


def assert_can_transition(ctx: TransitionContext, target: DeliveryStatus, *, force: bool = False) -> None:
    if force: return
    src = ctx.do.status
    allowed = _ALLOWED.get(src, set())
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition {src.value} → {target.value}",
            details={"from": src.value, "to": target.value, "allowed": [s.value for s in allowed]},
        )
```

Service 가 `assert_can_transition(ctx, target, force=body.force)` 호출 → 통과하면 status 업데이트.

세부: `src/delivery_order/CLAUDE.md`.

---

## 7. Dependencies / Const

### Dependencies

```
team/dependencies/
├── get_team_scope.py     # auth.team_id None 이면 400 TEAM_REQUIRED
└── (도메인 전용은 <domain>/dependencies/ 에)
```

`get_team_scope` 는 모든 팀 scoped 라우터가 공유:

```python
# team/dependencies/get_team_scope.py
async def get_team_scope(
    request: Request,
    _1: None = Depends(access_token),  # ← access_token 이 request.state.user 채움
) -> int:
    user = getattr(request.state, "user", None)
    if user is None:
        raise UnauthorizedException()
    team_id = request.headers.get("X-Team-Id")
    if not team_id:
        raise AppException(
            code="TEAM_REQUIRED", message="X-Team-Id 헤더 필요", status_code=400,
        )
    # user_teams 멤버십 검증 (캐시)
    ...
    return int(team_id)
```

### Const

- `<domain>/const/<file>.py` — Enum, 상수
- **쿼리 로직 금지** — 순수 상수 파일

```python
# delivery_order/const/status.py
from enum import Enum

class DeliveryStatus(str, Enum):
    PLANNING = "PLANNING"
    DISPATCHED = "DISPATCHED"
    YARD_STAGED = "YARD_STAGED"
    FINAL_DELIVERY = "FINAL_DELIVERY"
    EMPTY_STAGED = "EMPTY_STAGED"
    COMPLETED = "COMPLETED"

class ShipmentDirection(str, Enum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
```

---

## 8. PR 리뷰 체크리스트

**Model**
- [ ] `(Base, TeamScopedMixin)` 이중 상속 (팀 scoped 면)
- [ ] 라인 테이블은 `__with_team_rel__ = False`
- [ ] 같은 도메인 안 자식 FK 는 복합 FK `ForeignKeyConstraint(["team_id", "parent_id"], ...)`
- [ ] 도메인 간 FK 는 단순 FK + `ondelete=` (RESTRICT/SET NULL/CASCADE 비즈니스 의미별)
- [ ] `UniqueConstraint("team_id", "id")` 있음
- [ ] 복합 인덱스 전부 `team_id` leftmost
- [ ] Relationship `primaryjoin` 에 `foreign(X.team_id) == Y.team_id` 포함
- [ ] `models_registry.py` 에 import 추가
- [ ] DateTime 은 `DateTime(timezone=True)`
- [ ] 상태값은 `SAEnum(EnumClass, name="...")`
- [ ] `lazy=settings.ORM_LAZY_DEFAULT` (relationship)

**Repository**
- [ ] `TeamScopedRepoMixin` 상속
- [ ] `__init__(self, db, team_id)` + `super().__init__(team_id)`
- [ ] 모든 쿼리 `Model.team_id == self._require_team()` 첫 조건
- [ ] `.is_active.is_(True)` 명시 (또는 `include_inactive` 분기)
- [ ] `commit()` 호출 없음

**Service**
- [ ] `__init__(self, db, team_id, redis=None)` 시그니처
- [ ] 메서드에 team_id 파라미터 없음 (생성자로 이미 바인딩)
- [ ] Service → Service 직접 호출 없음 (Repository 직접 주입)
- [ ] 예외는 `AppException` 서브클래스 or 인라인
- [ ] `created_by_user_id` / `updated_by_user_id` 수동 세팅
- [ ] mutation 끝에 `_emit("<domain>.<action>", result)` 호출
- [ ] state 전이는 `state_machine.py` 의 함수 통과

**Router**
- [ ] `response_model=` 전 엔드포인트
- [ ] POST=201, DELETE=204 (또는 200+entity)
- [ ] Depends 순서 엄수: path → body → `access_token` → `permission_guard(...)` → `get_team_scope` → db → redis → `get_current_user`
- [ ] `_1` / `_2` sentinel 변수명
- [ ] mutation 라우터에 `permission_guard(...)` 부착
- [ ] GET=read_db, mutation=write_db
- [ ] mutation = `get_write_redis` 도 주입 (WS event 발행 위해)
- [ ] `ServiceClass(db, team_id, redis=redis)` 위치 인자
- [ ] `/sync` 라우터는 `/{<id>}` 보다 먼저 정의
- [ ] URL 에 team_id 있으면 path team_id 와 `get_team_scope` 결과 일치 검증

**Schema**
- [ ] `RequestSchema` / `ResponseSchema` 상속
- [ ] `<Verb><Resource>Request` / `<Resource>ResponseSchema` 접미사
- [ ] Update 전 필드 `Optional`
- [ ] Paginate 스키마 `BasePaginationSchema` 상속
- [ ] Bulk 는 `<Resource>Bulk<Verb>Request/ResponseSchema`
- [ ] State 전이는 `<Resource>TransitionRequest`
