# src/team/CLAUDE.md

⭐ **표준 도메인 모듈 레퍼런스.** 새 도메인이나 기존 도메인 수정 시 **이 파일의 규약을 그대로 따른다**. 복합 도메인(헤더/라인 + tasks)은 `src/ocean/CLAUDE.md`.

이 `team/` 자체는 **팀 루트 모델** (`TeamModel`, `UserTeamModel`) 을 담는 특수 도메인이라 `TeamScopedMixin` 은 안 쓰지만, 라우터/서비스/스키마 규약은 동일하게 적용된다.

---

## 0. 폴더 구조

```
<domain>/
├── __init__.py
├── model.py              # SQLAlchemy — (Base, TeamScopedMixin) 이중 상속이 기본
├── repository.py         # TeamScopedRepoMixin 상속
├── service.py            # __init__(db, team_id)
├── router.py             # Depends(get_team_scope)
├── schemas/
│   ├── __init__.py
│   ├── request.py        # RequestSchema 상속
│   └── response.py       # ResponseSchema 상속
├── dependencies/         # (옵션) 도메인 전용 FastAPI deps
└── const/                # (옵션) 도메인 상수 (enum 등)
```

---

## 1. Model 규약 — 팀 scoped 기본값

### 1-1. 상속 구조

```python
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin

class TagModel(Base, TeamScopedMixin):
    __tablename__ = "tags"
    ...
```

- **`(Base, TeamScopedMixin)` 이중 상속이 기본**
- `TeamScopedMixin` 이 자동 주입:
  - `team_id: Mapped[int]` (`FK → teams.id ondelete=CASCADE`, `index=True`, `nullable=False`)
  - `.team` relationship (`lazy="selectin"`)
- 라인 테이블 (예: `BundleLineModel`, `ContainerModel`) 은 `__with_team_rel__ = False` 로 `.team` 관계 제거 — 헤더 통해 접근

### 1-2. 팀 scoped 미상속 예외

다음 경우만 `TeamScopedMixin` 없이 `Base` 만 상속:
- 플랫폼 전역 유저 (`UserModel`)
- 팀 자체 (`TeamModel`)
- 조인 테이블로 team_id 가 의미 다른 경우 (`UserTeamModel` — team_id 도 있지만 user_id 와 동등 FK)
- 마스터 카탈로그 (`PermissionModel`)
- 폴리모픽 (`FileAssetModel` — team_id 는 있으나 `domain`+`object_id` 로 소유 결정)

### 1-3. 컬럼 규약

```python
name: Mapped[str]            = mapped_column(String(80), nullable=False)
email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
plan: Mapped[str]            = mapped_column(String(20), nullable=False, server_default="free")
amount: Mapped[Decimal]      = mapped_column(Numeric(18, 3), nullable=False, default=0, server_default="0")
memo: Mapped[Optional[str]]  = mapped_column(String(3000), nullable=True)
```

- SQLAlchemy 2.0 스타일 `Mapped[T] = mapped_column(...)`
- 타입 힌트와 `nullable` 일치 (`Optional[T]` ↔ `nullable=True`)
- **DateTime 은 항상 `DateTime(timezone=True)`** (서버 UTC 고정)
- 금액은 `Numeric(18, 3)`, 수량은 `Numeric(18, 4)` (샘플 관행)
- `server_default` (DB 기본값) vs `default` (Python 기본값) 구분

### 1-4. 복합 FK 제약 (**중요**)

팀 scoped 테이블 간의 FK 는 **반드시 복합 FK** 를 사용한다 — 크로스 팀 누출 방지.

```python
__table_args__ = (
    ForeignKeyConstraint(
        ["team_id", "parent_id"],
        ["parent_table.team_id", "parent_table.id"],
        ondelete="CASCADE",
        name="fk_child_parent_team_id_id",
    ),
    UniqueConstraint("team_id", "id", name="uq_child_team_id_id"),
    ...
)
```

**단순 FK `parent_id → parent_table.id` 금지.**

### 1-5. UniqueConstraint(team_id, id) 필수

```python
UniqueConstraint("team_id", "id", name="uq_<table>_team_id_id"),
```

- 복합 FK 의 **타겟** 이 되려면 `(team_id, id)` 가 unique 여야 함 (MySQL 제약)
- 도메인 유니크가 있다면 함께 선언: `UniqueConstraint("team_id", "sku", ...)`

### 1-6. 인덱스 — team_id leftmost

```python
Index("ix_<table>_team_id_id",   "team_id", "id"),
Index("ix_<table>_team_name",    "team_id", "name"),
Index("ix_<table>_team_status",  "team_id", "status"),
```

**모든 복합 인덱스는 `team_id` 가 첫 컬럼**. 팀 scoped 쿼리 (`WHERE team_id = ? ...`) 의 leftmost prefix 로 B-tree 효율 극대화.

### 1-6.5. Soft-Delete 정책 (통일)

- **모든 도메인 삭제는 `is_active=False`** — 별도 `deleted_at`/`revoked_at` 컬럼 추가 금지
- "언제 삭제됐는지" 는 `updated_at` (Base 가 `onupdate=func.now()` 자동 관리) 이 담당
- 삭제된 row 의 수정을 서비스 레벨에서 차단하면 `updated_at` ≈ 삭제 시점
- 팀/부모 삭제 시 자식 자동 정리는 DB FK `ondelete=CASCADE` 가 처리 (애플리케이션 코드 불필요)
- 예외: scraping upsert 시 UPDATE+INSERT 만 사용 (DELETE 도 안 씀 — `src/ocean/CLAUDE.md` 참조)

### 1-7. Relationship — primaryjoin 에 team_id 포함

#### 헤더 → 라인 (1:N, cascade 소유)

```python
containers = relationship(
    "ContainerModel",
    back_populates="shipment",
    cascade="all, delete-orphan",
    lazy=settings.ORM_LAZY_DEFAULT,           # "raise"
    order_by="ContainerModel.id.asc()",
    primaryjoin=lambda: and_(
        foreign(ContainerModel.team_id)     == ShipmentModel.team_id,   # ← 팀 매칭 필수
        foreign(ContainerModel.shipment_id) == ShipmentModel.id,
    ),
    passive_deletes=True,
)
```

#### 라인 → 헤더 (N:1)

```python
shipment = relationship(
    "ShipmentModel",
    back_populates="containers",
    lazy=settings.ORM_LAZY_DEFAULT,
    primaryjoin=lambda: and_(
        foreign(ContainerModel.team_id)     == ShipmentModel.team_id,
        foreign(ContainerModel.shipment_id) == ShipmentModel.id,
    ),
)
```

#### 뷰 전용 교차 관계 (viewonly)

```python
stocks: Mapped[List[StockModel]] = relationship(
    "StockModel",
    primaryjoin=lambda: and_(
        foreign(StockModel.team_id) == ProductModel.team_id,
        foreign(StockModel.product_id) == ProductModel.id,
        StockModel.is_active.is_(True),
    ),
    lazy=settings.ORM_LAZY_DEFAULT,
    viewonly=True,
    uselist=True,
)
```

#### 폴리모픽 파일 (discriminator)

```python
files: Mapped[list[FileAssetModel]] = relationship(
    "FileAssetModel",
    primaryjoin=lambda: and_(
        foreign(FileAssetModel.team_id) == ProductModel.team_id,
        FileAssetModel.domain == FileDomain.PRODUCT,
        foreign(FileAssetModel.object_id) == ProductModel.id,
    ),
    viewonly=True,
    lazy=settings.ORM_LAZY_DEFAULT,
)
```

#### `updated_by` 관계 (Base 의 FK 컬럼에 관계만 추가)

```python
updated_by: Mapped[Optional[UserModel]] = relationship(
    "UserModel",
    foreign_keys="TagModel.updated_by_user_id",
    lazy="raise",            # ← selectinload 명시적으로 강제
)
```

### 1-8. 순환 참조 회피

`ShipmentModel` 이 `ContainerModel` 을 참조하고 `ContainerModel` 도 `ShipmentModel` 을 참조하는 경우, Python import 순환을 피하려면 `primaryjoin=lambda: ...` 안에서 **지연 import** 사용:

```python
primaryjoin=lambda: and_(
    foreign(
        __import__("ocean.container.model", fromlist=["ContainerModel"]).ContainerModel.team_id
    ) == ShipmentModel.team_id,
    ...
),
```

또는 함수 헬퍼:
```python
def _Container():
    from ocean.container.model import ContainerModel
    return ContainerModel
```

---

## 2. Router 규약

### 2-1. APIRouter 설정

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/<domain>", tags=["<domain>"])
```

`main.py`에서 `app.include_router(team_router)` — prefix/tag 추가 금지.

### 2-2. 엔드포인트 규약

```python
@router.post("", response_model=TeamResponseSchema, status_code=201)
@router.get("/{team_id}", response_model=TeamResponseSchema)
@router.patch("/{team_id}", response_model=TeamResponseSchema)
@router.delete("/{team_id}/members/{user_id}", status_code=204)
```

- **`response_model=` 항상** (예외 없음)
- POST → `status_code=201`, DELETE → `status_code=204`, 나머지 암묵 200
- `summary`/`description`/`responses` 대신 함수 docstring
- path param 은 리소스명 포함 (`/{team_id}`, 단순 `/{id}` 금지)

### 2-3. Depends 주입 순서

팀 scoped 엔드포인트의 canonical 순서:

```python
@router.patch("/{tag_id}", response_model=TagResponseSchema)
async def update_tag(
    tag_id: int,                                            # 1. path params
    body: UpdateTagRequestSchema,                           # 2. body
    auth: AuthResult = Depends(jwt_or_api_key),            # 3. 인증
    _rl: None = Depends(rate_limit),                       # 4. rate limit
    team_id: int = Depends(get_team_scope),                # 5. 팀 스코프 ⭐
    me: UserResponseSchema = Depends(get_current_user),    # 6. 현재 유저 (필요 시)
    db: AsyncSession = Depends(get_write_db),              # 7. DB
):
    svc = TagService(db, team_id)                          # team_id 주입
    return await svc.update_tag(tag_id, body, updater_user_id=me.id)
```

**순서 고정**: path → body → `jwt_or_api_key` → `rate_limit` → `get_team_scope` → `get_current_user` → `get_{read|write}_db`.

- `get_team_scope` 는 `jwt_or_api_key` 뒤에 와야 함 (내부적으로 `auth.team_id` 를 참조)
- `get_current_user` 는 필요한 엔드포인트만
- path 에 team_id 가 있는 경우 (`/team/{team_id}/api-keys`) path 의 team_id 와 `get_team_scope` 결과가 일치하는지 라우터에서 검증 (URL 탬퍼링 방어)

### 2-4. DB 세션

| 작업 | Dependency |
| --- | --- |
| GET | `get_read_db` |
| POST / PATCH / DELETE | `get_write_db` |

**100% 엄격.** Service/Repository 는 `commit()` 호출 금지.

### 2-5. 서비스 인스턴스화

```python
svc = TagService(db, team_id)
return await svc.update_tag(tag_id, body, updater_user_id=me.id)
```

- 라우터 내부 인라인 — DI 프레임워크 안 씀
- **`(db, team_id)` 위치 인자** — 키워드 사용 금지
- 서비스 메서드에 team_id 를 다시 넣지 않음 — 생성자가 이미 바인딩

### 2-6. 반환 / 예외

- 라우터에서 `model_validate` 호출 금지 — 서비스가 Pydantic 반환
- `try/except` 최소 — `AppException` 전역 핸들러로 전파
- 외부 시스템 (Celery/Redis/OAuth redirect) 정리가 필요할 때만 라우터 try/except

### 2-7. 페이징

```python
@router.get("", response_model=CursorPaginationResult[TagResponseSchema])
async def list_tags(
    request: PaginateTagRequestSchema = Depends(),
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    svc = TagService(db, team_id)
    return await svc.list_paginated(request)
```

세부: `src/common/pagination/CLAUDE.md`.

---

## 3. Service 규약

### 3-1. 클래스 구조

```python
class TagService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.repo = TagRepository(db, team_id)
        # 교차 도메인은 Repository 직접 주입 (Service 직접 호출 금지)
        self.shipment_repo = ShipmentRepository(db, team_id)
```

- **반드시 클래스**. 모듈 레벨 함수 금지.
- `__init__(self, db, team_id)` 시그니처 고정 — 메서드마다 team_id 받지 않음
- Redis 도 필요하면 `__init__(self, db, team_id, redis)` 로 확장
- Primary repo 는 `self.repo` 로 고정
- 교차 도메인 repo 는 `self.<other>_repo` 네이밍

### 3-2. 교차 도메인 호출

- **Service → Service 직접 호출 금지** (순환 의존성 + 트랜잭션 경계 모호)
- 다른 도메인 필요 시 Repository 를 직접 주입
- 예외: 저장소 유틸 성격의 서비스 (예: `FileService`) 는 허용

### 3-3. 메서드 네이밍

| 동사 | 의미 | 반환 |
| --- | --- | --- |
| `create_*` | INSERT | Pydantic schema |
| `get_*` / `get_*_by_*` | 단건, 없으면 `NotFoundException` | Pydantic schema |
| `get_*_detail` | 관계 eager load 포함 | Pydantic schema |
| `list_*` / `list_*_paginated` | 컬렉션 | `List[Schema]` / `CursorPaginationResult[Schema]` |
| `update_*` | PATCH | Pydantic schema |
| `delete_*` | Soft delete (`is_active=False`) | `None` |
| `revoke_*` | 이력 보존 soft delete (`revoked_at`) — API Key 전용 | `None` |

**`find_*` 금지** — 전부 `get_*`.

### 3-4. 트랜잭션

- **`await self.db.commit()` 절대 호출 금지**
- `await self.db.flush()` + 필요 시 `await self.db.refresh(obj)`
- 예외는 `get_write_db` dependency 가 rollback 처리

예외적 이중 commit (Celery send_task 전) 패턴은 `src/ocean/CLAUDE.md` 참고.

### 3-5. 예외 raise

```python
from common.exceptions.base import (
    AppException, NotFoundException, ConflictException,
    ForbiddenException, BadRequestException,
)

raise NotFoundException("Tag")
raise ConflictException("이미 존재합니다.")

# 커스텀 코드 필요 시 인라인
raise AppException(
    code="TAG_LIMIT_EXCEEDED",
    message="팀당 최대 50개까지만 태그 생성 가능합니다.",
    status_code=status.HTTP_402_PAYMENT_REQUIRED,
)
```

도메인 전용 예외 파일 분리 금지 — 인라인 `AppException(code=...)` 권장.

### 3-6. Ownership 검사

- **Repository 의 `team_id` 필터가 기본 방어선** — 서비스 레이어에서 `if obj.team_id != self.team_id` 같은 검사는 **불필요** (리포가 이미 처리)
- 단, 리소스 소유 관계를 검증해야 할 때 (예: "이 shipment 의 container 인가") 는 추가 검사 필요

### 3-7. 감사 필드

`created_by_user_id` / `updated_by_user_id` 는 **서비스에서 수동 설정**:

```python
tag = TagModel(
    name=body.name,
    color=body.color,
    created_by_user_id=creator_user_id,
    updated_by_user_id=creator_user_id,
)
tag = await self.repo.create(tag)

# Update 시:
tag.updated_by_user_id = updater_user_id
await self.db.flush()
await self.db.refresh(tag)
```

`team_id` 는 리포가 자동 세팅하므로 Model 생성 시 생략 가능.

---

## 4. Repository 규약

**모든 규약은 `src/common/repository/CLAUDE.md` 참조** — 여기서는 요점만:

1. `TeamScopedRepoMixin` 상속
2. `__init__(self, db: AsyncSession, team_id: Optional[int])` + `super().__init__(team_id)`
3. 모든 쿼리에 `Model.team_id == self._require_team()` 첫 조건
4. Soft-delete 필터 `.is_active.is_(True)` 명시
5. `selectinload` (eager load), `joinedload` 금지
6. `create()` 내부에서 `obj.team_id = self._require_team()` 세팅
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

대규모 도메인도 이 2분할 유지 (verb별 파일 분리 금지).

### 5-2. 베이스 클래스

```python
from common.schemas.base import RequestSchema, ResponseSchema

class CreateTagRequestSchema(RequestSchema):
    name: str = Field(..., min_length=1, max_length=80)
    color: Optional[str] = Field(None, max_length=20)

class TagResponseSchema(ResponseSchema):
    id: int
    name: str
    color: Optional[str] = None
    created_at: datetime
```

- **`RequestSchema`** → `extra="forbid"`, `alias_generator=to_camel`, `populate_by_name=True`, `str_strip_whitespace=True`
- **`ResponseSchema`** → `from_attributes=True`, `extra="ignore"`, datetime 자동 UTC+Z 직렬화

### 5-3. 네이밍 — 엄격

| 접미사 | 용도 | 예 |
| --- | --- | --- |
| `<Verb><Resource>RequestSchema` | 요청 바디 | `CreateTagRequestSchema`, `UpdateTagRequestSchema` |
| `Paginate<Resource>RequestSchema` | 페이징 쿼리 | `PaginateTagRequestSchema` |
| `<Resource>ResponseSchema` | 단건 응답 | `TagResponseSchema` |
| `<Resource>ListItemResponseSchema` | 목록 아이템 (상세와 다를 때) | `UserListItemResponseSchema` |
| `<Resource>DetailResponseSchema` | 관계 포함 상세 | `ShipmentDetailResponseSchema` |

**`Schema` 접미사 누락 금지.**

### 5-4. Update 스키마

```python
class UpdateTagRequestSchema(RequestSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    color: Optional[str] = Field(None, max_length=20)
```

- 모든 필드 `Optional[...] = None`
- 서비스에서 `body.model_dump(exclude_unset=True)` 로 제공 필드만 적용

### 5-5. 페이징 요청

```python
from common.pagination.schemas.pagination_request import BasePaginationSchema

class PaginateTagRequestSchema(BasePaginationSchema):
    order__name: Optional[Literal["ASC", "DESC"]] = None
    where__name__i_like: Optional[str] = None
```

**`BasePaginationSchema` 상속 필수**. 세부: `src/common/pagination/CLAUDE.md`.

---

## 6. Dependencies / Const

- `dependencies/` — 도메인 전용 FastAPI deps (팀 전역 deps 는 `team/dependencies/get_team_scope.py` 이미 있으므로 중복 금지)
- `const/` — Enum, 상수. **쿼리 로직 금지** — 순수 상수 파일

---

## 7. PR 리뷰 체크리스트

**Model**
- [ ] `(Base, TeamScopedMixin)` 이중 상속 (팀 scoped 면)
- [ ] 라인 테이블은 `__with_team_rel__ = False`
- [ ] 자식 FK 는 복합 FK `ForeignKeyConstraint(["team_id", "parent_id"], ...)`
- [ ] `UniqueConstraint("team_id", "id")` 있음
- [ ] 복합 인덱스 전부 `team_id` leftmost
- [ ] Relationship `primaryjoin` 에 `foreign(X.team_id) == Y.team_id` 포함
- [ ] `models_registry.py` 에 import 추가
- [ ] DateTime 은 `DateTime(timezone=True)`
- [ ] `lazy=settings.ORM_LAZY_DEFAULT` (relationship)

**Repository**
- [ ] `TeamScopedRepoMixin` 상속
- [ ] `__init__(self, db, team_id)` + `super().__init__(team_id)`
- [ ] 모든 쿼리 `Model.team_id == self._require_team()` 첫 조건
- [ ] `.is_active.is_(True)` 명시
- [ ] `commit()` 호출 없음

**Service**
- [ ] `__init__(self, db, team_id)` 시그니처
- [ ] 메서드에 team_id 파라미터 없음 (생성자로 이미 바인딩)
- [ ] Service → Service 직접 호출 없음 (Repository 직접 주입)
- [ ] 예외는 `AppException` 서브클래스 or 인라인
- [ ] `created_by_user_id`/`updated_by_user_id` 수동 세팅

**Router**
- [ ] `response_model=` 전 엔드포인트
- [ ] POST=201, DELETE=204
- [ ] Depends 순서 엄수 (path → body → auth → rate_limit → get_team_scope → get_current_user → db)
- [ ] GET=read_db, mutation=write_db
- [ ] `ServiceClass(db, team_id)` 위치 인자
- [ ] URL 에 team_id 있으면 `_assert_scope(path_team_id, scoped_team_id)` 검증

**Schema**
- [ ] `RequestSchema`/`ResponseSchema` 상속
- [ ] `<Verb><Resource>RequestSchema` / `<Resource>ResponseSchema` 접미사
- [ ] Update 전 필드 `Optional`
- [ ] Paginate 스키마 `BasePaginationSchema` 상속
