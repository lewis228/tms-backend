# src/common/repository/CLAUDE.md

⭐ **Repository 계층 표준 인프라.** 모든 팀 scoped Repository 는 여기의 `TeamScopedRepoMixin` 을 상속해야 한다.

---

## 파일 구조

```
common/repository/
├── __init__.py
└── team_scoped.py    # TeamScopedRepoMixin, scope_by_team()
```

필요 시 `nested_columns.py` (도메인 간 공유 컬럼 상수), `base.py` (공통 베이스 클래스 등) 추가 가능.

---

## 1. `TeamScopedRepoMixin` — 팀 스코프 강제

### 시그니처

```python
class TeamScopedRepoMixin:
    def __init__(self, team_id: Optional[int]):
        self.team_id = team_id

    def _require_team(self) -> int:
        """팀 scoped 연산에 team_id 필수임을 보장. None 이면 ValueError."""
        if self.team_id is None:
            raise ValueError("team_id is required for this repository operation")
        return self.team_id

    @staticmethod
    def _scope(q: Select, col: InstrumentedAttribute, team_id: int) -> Select:
        return q.where(col == team_id)
```

### 사용 규약

모든 팀 scoped 도메인 레포는 다음 패턴:

```python
class DeliveryOrderRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db
        self._common_service = CommonService()

    async def get(self, do_id: int) -> Optional[DeliveryOrderModel]:
        stmt = select(DeliveryOrderModel).where(
            DeliveryOrderModel.team_id == self._require_team(),   # ← WHERE 첫 조건
            DeliveryOrderModel.id == do_id,
            DeliveryOrderModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)
```

**핵심 규칙**:
1. `__init__(self, db: AsyncSession, team_id: Optional[int])` — 파라미터 순서 고정
2. `super().__init__(team_id)` 반드시 호출
3. **모든 쿼리의 WHERE 첫 조건**으로 `Model.team_id == self._require_team()` 추가
4. `create()` 메서드는 ORM 객체 저장 전 `payload["team_id"] = self._require_team()` 강제 세팅
5. `team_id=None` 으로 생성된 인스턴스는 `_require_team()` 이 즉시 실패 — 개발 시점에 빠르게 감지

### 팀 scoped 가 아닌 Repository 예외

아래는 `TeamScopedRepoMixin` 상속하지 않음:
- `UserRepository` — 글로벌 유저 모델
- `TeamRepository` — 팀 자체의 CRUD (team_id 로 scoped 아님)
- `AuthRepository` — Redis 전용
- `FileService` — 폴리모픽 파일 (team_id 는 있지만 domain+object_id 로 소유 결정)
- `RbacRepository` — permissions 마스터는 글로벌, 그룹은 팀 scoped 인데 redis 캐시 통합 위해 별도 패턴
- `DistanceMatrixRepository` — 글로벌 거리 매트릭스 (캐시)

이외 **모든** 비즈니스 도메인 레포는 상속 필수.

---

## 2. ApiKeyRepository 의 예외 처리 (인증 시점)

API Key 인증은 **team_id 를 모르는 상태**에서 키 문자열만으로 진입한다. 따라서 `ApiKeyRepository` 는 `team_id=None` 으로도 생성 가능하며, **두 메서드만** 그 상태에서 호출 가능:

```python
# auth/dependencies/jwt_or_api_key.py
auth_repo = ApiKeyRepository(db, team_id=None)          # ← None 허용
key_row = await auth_repo.get_active_by_key(key_str)    # _require_team() 호출 안 함
await auth_repo.touch_last_used(key_row.id)             # 동일
```

이 두 메서드는 `_require_team()` 을 호출하지 않도록 구현. 다른 메서드 (`get_by_id`, `list_by_team`, `create`) 는 호출 시 ValueError.

**이 패턴을 다른 도메인에서 따라하지 말 것** — 인증 핫 패스의 특수 사례.

---

## 3. 시스템 모드 / Celery Task

Celery Beat 처럼 **전 팀을 스캔**해야 하는 경우, `TeamScopedRepoMixin` 을 우회한다:

**방식 A — Raw SQLAlchemy Core (현재 권장)**
```python
# notification/tasks/dispatch_pending.py
with _SessionLocal() as db:
    notifications = db.execute(
        select(NotificationModel).where(
            NotificationModel.is_active.is_(True),
            NotificationModel.dispatched_at.is_(None),
            NotificationModel.created_at > cutoff,
        )
    ).scalars().all()
```
- 시스템 의도를 명시적으로 드러냄 (팀 필터 없음 = 의도된 전역 스캔)
- sync 세션 기반 (Celery worker 는 async lifespan 없음)

**방식 B — SystemXxxRepository (필요 시 추가)**

만약 시스템 모드 쿼리가 많아지면 도메인별로 `SystemNotificationRepository(db)` 를 따로 만들어 `TeamScopedRepoMixin` 없이 구성. 현재는 Beat task 가 적어 방식 A 로 충분.

---

## 4. Eager Loading 전략

### 인라인 (간단한 도메인)

```python
async def get_with_containers(self, do_id: int) -> Optional[DeliveryOrderModel]:
    stmt = (
        select(DeliveryOrderModel)
        .options(
            selectinload(DeliveryOrderModel.containers),
            selectinload(DeliveryOrderModel.customer),
        )
        .where(
            DeliveryOrderModel.team_id == self._require_team(),
            DeliveryOrderModel.id == do_id,
            DeliveryOrderModel.is_active.is_(True),
        )
    )
    return await self.db.scalar(stmt)
```

### 헬퍼 메서드 (관계 많은 도메인)

```python
class DeliveryOrderRepository(TeamScopedRepoMixin):
    def _with_options_detail(self):
        return [
            selectinload(DeliveryOrderModel.containers).options(
                selectinload(ContainerModel.legs),
            ),
            selectinload(DeliveryOrderModel.customer),
            selectinload(DeliveryOrderModel.terminal),
            selectinload(DeliveryOrderModel.vessel),
            selectinload(DeliveryOrderModel.files).options(load_only(*FILE_NESTED_COLS)),
            with_loader_criteria(ContainerModel, ContainerModel.is_active.is_(True)),
        ]

    def _with_options_minimal(self):
        return [load_only(DeliveryOrderModel.id, DeliveryOrderModel.team_id, ...)]
```

`load_only` 용 컬럼 상수 묶음은 `common/repository/nested_columns.py` (필요 시 생성) 에 모은다.

### 절대 금지

- `joinedload` — 카테시안 곱 위험. 항상 `selectinload`.
- `lazy="joined"` 또는 `lazy="select"` — `ORM_LAZY_DEFAULT="raise"` 가 잡아주지만, 실수로 N+1 폭발.

---

## 5. Write 동작 규약

- **`commit()` 절대 호출 금지** — `get_write_db` dependency 가 yield 후 자동 commit
- Insert: `db.add(obj)` → `await db.flush()` → `await db.refresh(obj)` → return obj
- Update: ORM 인스턴스 수정 후 `await db.flush()` (필요 시 refresh)
- 대량 업데이트: `update(Model).where(team_id=...).values(...)` + `execute()`

**Celery task 내부**: sync 세션은 dependency 가 관리 안 하므로 직접 `db.commit()` 호출 필요.

### create 패턴 — payload dict 기반

```python
async def create(self, payload: dict, actor_user_id: int | None = None) -> DeliveryOrderModel:
    payload["team_id"] = self._require_team()
    if actor_user_id is not None:
        payload["created_by_user_id"] = actor_user_id
    row = DeliveryOrderModel(**payload)
    self.db.add(row)
    await self.db.flush()
    await self.db.refresh(row)
    return row
```

- service 가 `body.model_dump(exclude_unset=True)` 로 dict 전달 → repository 가 `team_id` / `created_by_user_id` 주입
- ORM 객체 직접 만들기 → `repo.add(obj)` 식보다 dict 패턴이 더 안전 (모든 도메인이 동일 시그니처)

### bulk create

```python
async def create_many(
    self, payloads: List[dict], actor_user_id: int | None = None,
) -> List[DeliveryOrderModel]:
    team_id = self._require_team()
    rows = []
    for payload in payloads:
        payload["team_id"] = team_id
        if actor_user_id is not None:
            payload["created_by_user_id"] = actor_user_id
        row = DeliveryOrderModel(**payload)
        self.db.add(row)
        rows.append(row)
    await self.db.flush()
    for row in rows:
        await self.db.refresh(row)
    return rows
```

---

## 6. 메서드 네이밍 표준

| 패턴 | 반환 | 용도 |
| --- | --- | --- |
| `get(id)` 또는 `get_by_id(id)` | `Optional[Model]` | PK 조회 |
| `get_by_<field>(val)` | `Optional[Model]` | 자연키 조회 |
| `get_<x>_with_relations(id)` | `Optional[Model]` | eager load 포함 |
| `get_detail(id)` | `Optional[Model]` | 풀 디테일 (모든 관계 eager load) |
| `list_by_team()` | `Sequence[Model]` | 팀 전체 (bounded 보장) |
| `list_by_<parent_field>(val)` | `Sequence[Model]` | 부모별 |
| `list_paginated(request)` | `CursorPaginationResult[Model]` | 페이징 |
| `exists_<field>(val)` | `bool` | 존재 여부 |
| `create(payload, actor_user_id)` | `Model` | INSERT + flush + refresh |
| `create_many(payloads)` | `List[Model]` | bulk INSERT |
| `update(id, payload, actor_user_id)` | `Model` | UPDATE + flush + refresh |
| `touch_<field>(id)` | `None` | 단일 필드 업데이트 (핫 패스) |
| `delete_by_<field>(val)` | `None` | 하드 삭제 (특수 — 일반은 service 가 soft) |
| `soft_delete(id, actor_user_id)` | `Model` | is_active=False + return entity (DELETE 응답용) |

**`find_*` 사용 금지** — 전부 `get_*` 또는 `list_*`.

---

## 7. 트랜잭션 / 동시성

### 일반 패턴 — service 가 단일 트랜잭션 단위

```python
# service.py
async def create_with_lines(self, body) -> DOResponseSchema:
    do = await self.repo.create({...})              # flush 만, commit X
    lines = await self.repo.create_lines(do.id, [...])  # flush 만
    # get_write_db 가 yield 후 한 번에 commit
    return DOResponseSchema.model_validate(do)
```

### 동시 update 충돌 — 낙관적 잠금 (필요 시)

```python
# version 컬럼 활용
class XModel(Base, TeamScopedMixin):
    version: Mapped[int] = mapped_column(default=1, server_default="1")

async def update_with_version(self, x_id: int, expected_version: int, payload: dict):
    stmt = (
        update(XModel)
        .where(XModel.team_id == self._require_team(), XModel.id == x_id, XModel.version == expected_version)
        .values(**payload, version=XModel.version + 1)
    )
    result = await self.db.execute(stmt)
    if result.rowcount == 0:
        raise AppException(code="VERSION_CONFLICT", message="...", status_code=409)
```

### Celery 와의 동기화 — 이중 commit (예외)

Service / Router 에서 `commit()` 은 원칙적으로 금지지만 **Celery 워커가 방금 INSERT 한 row 를 읽어야 하는 경우**:

```python
# router.py
@router.post("", response_model=DOResponseSchema)
async def create_do(...):
    do = await DeliveryOrderService(db, team_id).create(body, ...)

    # Celery worker 가 이미 커밋된 row 를 읽어야 하므로 send_task 전 명시적 commit.
    await db.commit()

    celery.send_task("notification.tasks.send_dispatch_alert", kwargs={"do_id": do.id})
    return do
```

**다른 도메인에서 흉내내지 말 것** — Celery 동기화 만 예외.

---

## 8. PR 리뷰 체크리스트

- [ ] `TeamScopedRepoMixin` 상속했다 (팀 scoped 도메인이면)
- [ ] `__init__(self, db: AsyncSession, team_id: Optional[int])` 시그니처
- [ ] `super().__init__(team_id)` 호출
- [ ] 모든 쿼리에 `Model.team_id == self._require_team()` 있다
- [ ] Soft-delete 필터 `.is_active.is_(True)` 명시적 (또는 `include_inactive` 분기)
- [ ] `selectinload` 사용, `joinedload` 금지
- [ ] `commit()` 호출 없음 (sync session / Celery 동기화 제외)
- [ ] 네이밍 `get_*` / `list_*` / `create` / `touch_*` — `find_*` 없음
- [ ] 페이징은 `CommonService.paginate()` 경유
- [ ] `create()` 에서 `payload["team_id"] = self._require_team()` 주입
- [ ] `delete()` 또는 `soft_delete()` 후 `db.refresh(obj)` 로 reload (DELETE 응답에 entity 반환 위해)
