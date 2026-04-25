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
class ShipmentRepository(TeamScopedRepoMixin):
    def __init__(self, db: AsyncSession, team_id: Optional[int]):
        super().__init__(team_id)
        self.db = db

    async def get(self, shipment_id: int) -> Optional[ShipmentModel]:
        stmt = select(ShipmentModel).where(
            ShipmentModel.team_id == self._require_team(),   # ← WHERE 첫 조건
            ShipmentModel.id == shipment_id,
            ShipmentModel.is_active.is_(True),
        )
        return await self.db.scalar(stmt)
```

**핵심 규칙**:
1. `__init__(self, db: AsyncSession, team_id: Optional[int])` — 파라미터 순서 고정
2. `super().__init__(team_id)` 반드시 호출
3. **모든 쿼리의 WHERE 첫 조건**으로 `Model.team_id == self._require_team()` 추가
4. `create()` 메서드는 ORM 객체 저장 전 `obj.team_id = self._require_team()` 강제 세팅
5. `team_id=None` 으로 생성된 인스턴스는 `_require_team()` 이 즉시 실패 — 개발 시점에 빠르게 감지

### 팀 scoped 가 아닌 Repository 예외

아래는 `TeamScopedRepoMixin` 상속하지 않음:
- `UserRepository` — 글로벌 유저 모델
- `TeamRepository` — 팀 자체의 CRUD (team_id 로 scoped 아님)
- `AuthRepository` — Redis 전용
- `FileService` — 폴리모픽 파일 (team_id 는 있지만 domain+object_id 로 소유 결정)

이외 **모든** 도메인 레포는 상속 필수.

---

## 2. ApiKeyRepository 의 예외 처리 (인증 시점)

API Key 인증은 **team_id 를 모르는 상태**에서 키 문자열만으로 진입한다. 따라서 `ApiKeyRepository` 는 `team_id=None` 으로도 생성 가능하며, **두 메서드만** 그 상태에서 호출 가능:

```python
# auth/dependencies/jwt_or_api_key.py
auth_repo = ApiKeyRepository(db, team_id=None)          # ← None 허용
key_row = await auth_repo.get_active_by_key(key_str)    # _require_team() 호출 안 함
await auth_repo.touch_last_used(key_row.id)             # 동일
```

이 두 메서드는 `_require_team()` 을 호출하지 않도록 구현. 다른 메서드(`get_by_id`, `list_by_team`, `create`)는 호출 시 ValueError.

**이 패턴을 다른 도메인에서 따라하지 말 것** — 인증 핫 패스의 특수 사례.

---

## 3. 시스템 모드 / Celery Task

Celery Beat 처럼 **전 팀을 스캔**해야 하는 경우, `TeamScopedRepoMixin` 을 우회한다:

**방식 A — Raw SQLAlchemy Core (현재 권장)**
```python
# ocean/tasks/scheduling.py
with _SessionLocal() as db:
    shipments = db.execute(
        select(ShipmentModel).where(
            ShipmentModel.is_active.is_(True),
            ShipmentModel.next_scrape_at <= now,
        )
    ).scalars().all()
```
- 시스템 의도를 명시적으로 드러냄 (팀 필터 없음 = 의도된 전역 스캔)
- sync 세션 기반 (Celery worker 는 async lifespan 없음)

**방식 B — SystemXxxRepository (필요 시 추가)**

만약 시스템 모드 쿼리가 많아지면 도메인별로 `SystemShipmentRepository(db)` 를 따로 만들어 `TeamScopedRepoMixin` 없이 구성. 하지만 현재는 Beat task 하나 뿐이라 방식 A 로 충분.

---

## 4. Eager Loading 전략 (선택적)

간단한 도메인은 `selectinload(...)` 를 쿼리마다 인라인. 관계가 많아지면 샘플 레포(`backend_sample`)처럼 3단 헬퍼로 캐싱:

```python
class ProductRepository(TeamScopedRepoMixin):
    def _with_options_detail(self):
        return [
            load_only(*PRODUCT_BASE_COLS),
            selectinload(ProductModel.attributes).options(...),
            selectinload(ProductModel.stocks).options(...),
            selectinload(ProductModel.files).options(load_only(*FILE_NESTED_COLS)),
            with_loader_criteria(AttributeValueModel, AttributeValueModel.is_active.is_(True)),
        ]

    def _with_options_minimal(self):
        return [load_only(ProductModel.id, ProductModel.team_id, ...)]

    def _with_options_deleted(self):
        ...
```

**현재 tracking-api** 는 도메인 관계가 얕아서 인라인으로 충분. 관계 깊이가 늘면 도입.

`load_only` 용 컬럼 상수 묶음은 `common/repository/nested_columns.py` (필요 시 생성) 에 모은다.

---

## 5. Write 동작 규약

- **`commit()` 절대 호출 금지** — `get_write_db` dependency 가 yield 후 자동 commit
- Insert: `db.add(obj)` → `await db.flush()` → `await db.refresh(obj)` → return obj
- Update: ORM 인스턴스 수정 후 `await db.flush()` (필요 시 refresh)
- 대량 업데이트: `update(Model).where(team_id=...).values(...)` + `execute()`

**Celery task 내부**: sync 세션은 dependency 가 관리 안 하므로 직접 `db.commit()` 호출 필요.

---

## 6. 메서드 네이밍 표준

| 패턴 | 반환 | 용도 |
| --- | --- | --- |
| `get_by_id(id)` | `Optional[Model]` | PK 조회 |
| `get_by_<field>(val)` | `Optional[Model]` | 자연키 조회 |
| `get_<x>_by_<field>_with_relations(val)` | `Optional[Model]` | eager load 포함 |
| `list_by_team()` | `Sequence[Model]` | 팀 전체 (bounded) |
| `list_by_<parent_field>(val)` | `Sequence[Model]` | 부모별 |
| `list_paginated(request)` | `CursorPaginationResult[Model]` | 페이징 |
| `exists_<field>(val)` | `bool` | 존재 여부 |
| `create(model)` | `Model` | INSERT + flush + refresh |
| `touch_<field>(id)` | `None` | 단일 필드 업데이트 (핫 패스) |
| `delete_by_<field>(val)` | `None` | 하드 삭제 (upsert 첫 단계 등) |

**`find_*` 사용 금지** — 전부 `get_*`.

---

## 7. 체크리스트 (PR 리뷰)

- [ ] `TeamScopedRepoMixin` 상속했다 (팀 scoped 도메인이면)
- [ ] `__init__(self, db: AsyncSession, team_id: Optional[int])` 시그니처
- [ ] `super().__init__(team_id)` 호출
- [ ] 모든 쿼리에 `Model.team_id == self._require_team()` 있다
- [ ] Soft-delete 필터 `.is_active.is_(True)` 명시적
- [ ] `selectinload` 사용, `joinedload` 금지
- [ ] `commit()` 호출 없음 (sync session 제외)
- [ ] 네이밍 `get_*` / `list_*` / `create` / `touch_*` — `find_*` 없음
- [ ] 페이징은 `CommonService.paginate()` 경유
