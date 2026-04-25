# src/ocean/CLAUDE.md

⭐ **복합 도메인 템플릿.** 헤더 + 여러 라인 서브리소스 + Celery tasks 가 필요한 도메인의 레퍼런스. `air/`, `rail/`, `terminal/` 도 같은 구조로 확장. 단일 리소스 도메인은 `src/team/CLAUDE.md`.

---

## 0. 폴더 구조

```
ocean/
├── shipment/               # 최상위 헤더
│   ├── model.py
│   ├── repository.py
│   ├── service.py
│   ├── router.py           # 2개 router (scoped + public track)
│   └── schemas/
├── container/              # 라인 (shipment 자식)
├── tracking_event/         # 라인 (shipment 자식, optional container_id)
├── scrape_log/             # 라인 (shipment 자식, 이력)
└── tasks/                  # Celery 공유 태스크
    └── scheduling.py
```

각 서브리소스는 표준 도메인 규약 (`src/team/CLAUDE.md`) 을 따르고 이 파일은 **복합 도메인 고유 규약**만 담는다.

---

## 1. 네이밍 규약 (도메인 접두사)

### 테이블

모든 ocean 내 테이블은 `ocean_` prefix:

```python
__tablename__ = "ocean_shipments"
__tablename__ = "ocean_containers"
__tablename__ = "ocean_container_events"
__tablename__ = "ocean_scrape_logs"
__tablename__ = "ocean_shipment_tags"
```

`air_`, `rail_`, `terminal_` 도 동일 패턴. 네임스페이스 충돌 방지.

### 모델 클래스

**prefix 없이** — 패키지 경로가 네임스페이스 담당:

```python
# ocean/shipment/model.py
class ShipmentModel(Base, TeamScopedMixin): ...   # OceanShipmentModel 아님

# air/shipment/model.py (향후)
class ShipmentModel(Base, TeamScopedMixin): ...
```

`models_registry.py` 에선 모듈 경로 명시 import:
```python
from ocean.shipment.model import ShipmentModel
# from air.shipment.model import ShipmentModel as AirShipmentModel  # 추후
```

### 인덱스/FK 네이밍

`ix_<table>_<cols>`, `uq_<table>_<cols>`, `fk_<table>_<ref>_<cols>`:
```python
Index("ix_ocean_shipments_team_id_id", ...),
UniqueConstraint("team_id", "mbl", name="uq_ocean_shipments_team_mbl"),
ForeignKeyConstraint(..., name="fk_ocean_containers_shipment_team_id_id"),
```

---

## 2. 라우터 중첩 prefix

### 헤더 (shipment)

```python
router = APIRouter(prefix="/api/v1/ocean/shipments", tags=["shipment"])
track_router = APIRouter(prefix="/api/v1/ocean", tags=["track"])  # 보조
```

### 라인 (container, tracking_event, scrape_log)

부모 경로 아래 중첩:
```python
router = APIRouter(
    prefix="/api/v1/ocean/shipments/{shipment_id}/containers",
    tags=["container"],
)

router = APIRouter(
    prefix="/api/v1/ocean/shipments/{shipment_id}/events",
    tags=["tracking_event"],
)

router = APIRouter(
    prefix="/api/v1/ocean/shipments/{shipment_id}/scrape-logs",
    tags=["scrape_log"],
)
```

`main.py` 에서 각각 `include_router`. 서브리소스 라우터도 **`Depends(get_team_scope)` 필수**.

### Dual router 패턴 (shipment/router.py)

```python
router = APIRouter(prefix="/api/v1/ocean/shipments", tags=["shipment"])
# 팀 scoped CRUD
track_router = APIRouter(prefix="/api/v1/ocean", tags=["track"])
# 공개 조회 전용 (MBL 바로 → /track?mbl=...)
```

둘 다 `jwt_or_api_key` + `get_team_scope` 적용 (API Key 호출자의 team 데이터만 반환).

---

## 3. Model 규약 — 복합 FK

### 3-1. 헤더 (ShipmentModel)

```python
class ShipmentModel(Base, TeamScopedMixin):
    __tablename__ = "ocean_shipments"

    mbl: Mapped[str] = mapped_column(String(50), nullable=False)
    # ... 필드들 ...

    containers = relationship(
        "ContainerModel",
        back_populates="shipment",
        cascade="all, delete-orphan",
        lazy=settings.ORM_LAZY_DEFAULT,
        order_by="ContainerModel.id.asc()",
        primaryjoin=lambda: and_(
            foreign(ContainerModel.team_id) == ShipmentModel.team_id,
            foreign(ContainerModel.shipment_id) == ShipmentModel.id,
        ),
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("team_id", "id",  name="uq_ocean_shipments_team_id_id"),
        UniqueConstraint("team_id", "mbl", name="uq_ocean_shipments_team_mbl"),    # 팀당 MBL unique
        Index("ix_ocean_shipments_team_id_id",            "team_id", "id"),
        Index("ix_ocean_shipments_team_mbl",              "team_id", "mbl"),
        Index("ix_ocean_shipments_team_status",           "team_id", "status"),
        Index("ix_ocean_shipments_team_next_scrape_at",   "team_id", "next_scrape_at"),
        Index("ix_ocean_shipments_next_scrape_at",        "next_scrape_at"),  # Beat 전역 스캔용
    )
```

**중요 포인트**:
- `mbl` 은 팀당 unique (글로벌 unique 아님) — 다른 팀이 같은 MBL 독립 추적 허용
- `next_scrape_at` 에는 전역 인덱스 **추가** — Beat task 가 team 무관 스캔하므로

### 3-2. 라인 (ContainerModel, TrackingEventModel, ScrapeLogModel, OceanShipmentTagModel)

```python
class ContainerModel(Base, TeamScopedMixin):
    __tablename__ = "ocean_containers"
    __with_team_rel__ = False                    # ← 라인은 .team 관계 제거

    shipment_id: Mapped[int] = mapped_column(Integer, nullable=False)   # ← ForeignKey 없이
    # ... 필드들 ...

    shipment = relationship(
        "ShipmentModel",
        back_populates="containers",
        lazy=settings.ORM_LAZY_DEFAULT,
        primaryjoin=lambda: and_(
            foreign(ContainerModel.team_id)     == ShipmentModel.team_id,
            foreign(ContainerModel.shipment_id) == ShipmentModel.id,
        ),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "shipment_id"],
            ["ocean_shipments.team_id", "ocean_shipments.id"],
            ondelete="CASCADE",
            name="fk_ocean_containers_shipment_team_id_id",
        ),
        UniqueConstraint("team_id", "id", name="uq_ocean_containers_team_id_id"),
        Index("ix_ocean_containers_team_id_id",       "team_id", "id"),
        Index("ix_ocean_containers_team_shipment",    "team_id", "shipment_id"),
        Index("ix_ocean_containers_team_number",      "team_id", "number"),
    )
```

**중요 포인트**:
- `shipment_id` 컬럼은 **단순 Integer** — FK 제약은 `__table_args__` 에서 복합으로
- 컬럼 레벨 `ForeignKey(...)` 사용 금지
- `primaryjoin` 에 반드시 `team_id` 매칭 포함
- 이렇게 하면 다른 팀 shipment 에 엮인 container 는 DB에서도 ORM에서도 금지

### 3-3. FK ondelete 정책

| 관계 | ondelete | 이유 |
| --- | --- | --- |
| `team_id` → `teams.id` (`TeamScopedMixin` 기본) | CASCADE | 팀 삭제 → 하위 전부 정리 |
| 라인 → 헤더 (`shipment_id` 복합 FK) | CASCADE | 헤더 삭제 → 라인 전부 정리 |
| 참조 테이블 (`tag_id` → `tags`) | RESTRICT | 사용 중 태그 하드 삭제 차단 |
| 감사 필드 (`created_by_user_id`) | RESTRICT (Base 기본) | 사용자 하드 삭제 차단 |

---

## 4. Repository 패턴

모든 ocean 레포 (`ShipmentRepository`, `ContainerRepository`, ...) 는 `TeamScopedRepoMixin` 상속. 세부는 `src/common/repository/CLAUDE.md`.

### 스크래핑 upsert — UPDATE 기반 (DELETE 없음)

**원칙**: 사용자 삭제는 soft (`is_active=False`), 스크래핑은 항상 UPDATE+INSERT. 하드 삭제는 DB CASCADE 시에만.

컨테이너 upsert 는 scraping 레포(`backend_scraping/src/ocean/database.py`) 의 `save_tracking_result()` 에서 처리:

```python
# 1) 기존 컨테이너 맵 로드
existing = {c.number: c for c in session.query(ContainerRecord)
             .filter(team_id=tid, shipment_id=sid, is_active=True).all()}

# 2) 응답 컨테이너별 upsert
for c in result.containers:
    if c.number in existing:
        # UPDATE — id 유지 → ocean_container_events FK 도 유지
        row = existing[c.number]
        row.status = result.status
        row.terminal = result.terminal
        # ...
    else:
        # INSERT
        session.add(ContainerRecord(...))

# 3) 응답에 없는 기존 컨테이너 → 그대로 둠 (옵션 B: "한 번 확인된 건 보존")
```

이벤트는 **append-only + dedup** (`(timestamp, location, description)` 키로 중복 제거).

**왜 UPDATE 기반?**
- `container.id` 유지 → `ocean_container_events.container_id` FK 가 끊기지 않음
- `updated_at` 이 실제 변경된 row 만 갱신 → 의미있는 타임스탬프
- 이벤트 이력 축적 가능 (DELETE+CASCADE 였다면 매 스크랩마다 날아감)
- IO 비용 ↓ (변경된 컬럼만 UPDATE)

---

## 5. 즉시 디스패치 (Router 레벨)

사용자가 MBL 등록하면 Beat 주기를 기다리지 않고 즉시 스크래핑:

```python
@router.post("", response_model=ShipmentResponseSchema, status_code=201)
async def create_shipment(
    body: CreateShipmentRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    svc = ShipmentService(db, team_id)
    result = await svc.create_shipment(body)

    # Celery worker 가 이미 커밋된 row 를 읽어야 하므로 send_task 전 명시적 commit.
    # get_write_db 가 yield 후 한 번 더 commit 해도 no-op.
    await db.commit()

    # 중복 방지 락 (Redis SET NX)
    lock_key = f"{SCRAPE_LOCK_PREFIX}{result.mbl}"
    acquired = await redis_client.set(lock_key, "1", ex=SCRAPE_LOCK_TTL, nx=True)
    if acquired:
        try:
            celery.send_task(
                "ocean.tasks.scrape.scrape_mbl",
                kwargs={"shipment_id": result.id, "mbl": result.mbl, "carrier": result.carrier},
                queue="scraping-ocean",
            )
        except Exception:
            # send_task 실패 시 고아 락 방지
            try:
                await redis_client.delete(lock_key)
            except Exception:
                pass
            raise
    return result
```

**이중 commit 패턴**: Service/Router 에서 `commit()` 은 원칙적으로 금지지만 **Celery 워커 동기화** 만은 예외. 다른 도메인에서 흉내내지 말 것.

---

## 6. Celery Tasks — 시스템 모드

### 6-1. Task 이름

```python
@celery.task(name="ocean.tasks.scheduling.check_and_schedule_scrapes")
```

형식: `<domain>.tasks.<file>.<function>`. `celery_app.py` 의 `imports=["ocean.tasks.scheduling"]` 에 등록.

### 6-2. Sync Session (FastAPI async 와 분리)

Celery worker 는 FastAPI 요청 스코프를 갖지 않아서 **자체 sync 세션**:

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

def _build_sync_dsn() -> str:
    host = settings.DB_WRITE_HOST if settings.is_db_read_write_split else settings.DB_HOST
    return f"mysql+pymysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}@{host}:{settings.DB_PORT}/{settings.DB_DATABASE}?charset=utf8mb4"

_engine = create_engine(_build_sync_dsn(), pool_size=5, pool_pre_ping=True, pool_recycle=1800)

@event.listens_for(_engine, "connect")
def _set_utc(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    try:
        cur.execute("SET time_zone = '+00:00'")
    finally:
        cur.close()

_SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
```

**주의**:
- `mysql+pymysql://` (sync). Async 는 `aiomysql`.
- UTC 이벤트 훅 필수.
- task 내부에서 **명시적 `db.commit()` 호출** (dependency 없음).

### 6-3. 시스템 모드 — `TeamScopedRepoMixin` 우회

Beat task 는 **전 팀을 스캔** 하므로 `TeamScopedRepoMixin` 의 `_require_team()` 과 맞지 않음. Raw SQLAlchemy Core 직접 사용:

```python
@celery.task(name="ocean.tasks.scheduling.check_and_schedule_scrapes")
def check_and_schedule_scrapes() -> dict:
    now = datetime.now(timezone.utc)
    dispatched, skipped = 0, 0
    with _SessionLocal() as db:
        shipments = db.execute(
            select(ShipmentModel).where(
                ShipmentModel.is_active.is_(True),
                ShipmentModel.next_scrape_at.isnot(None),
                ShipmentModel.next_scrape_at <= now,
            )
        ).scalars().all()

        for shipment in shipments:
            # ... 락 획득 + send_task + next_scrape_at 갱신 ...
            pass

        db.commit()
    return {"dispatched": dispatched, "skipped": skipped, "checked_at": now.isoformat()}
```

**시스템 모드 원칙**:
- Beat/cron 성격의 전역 스캔 작업은 Raw Core 로 — 팀 필터 없음이 **의도된 동작**
- 특정 팀 task (예: "팀 X 의 모든 shipment 재스크랩") 이라면 일반 Repository 사용 + `team_id` 명시 전달

### 6-4. 분산 락 (중복 방지)

```python
_redis = sync_redis.Redis(...)
SCRAPE_LOCK_PREFIX = "scraping:lock:"
SCRAPE_LOCK_TTL = 600   # 10분 — 스크래핑 최대 실행 시간

lock_key = f"{SCRAPE_LOCK_PREFIX}{shipment.mbl}"
acquired = _redis.set(lock_key, "1", ex=SCRAPE_LOCK_TTL, nx=True)
if not acquired:
    logger.info("Skipping MBL %s — scraping lock exists", shipment.mbl)
    skipped += 1
    continue
```

**팀 간 공유 락**: MBL 이 팀당 unique 이긴 하지만 `scrape_lock:MBL_STRING` 키는 글로벌. 두 팀이 같은 MBL 을 추적해도 **캐리어 웹사이트 스크래핑 중복 방지**가 우선. 이는 의도된 설계.

**락 해제 책임**: scraping 워커 (scraping repo) 가 결과 저장 후 `_redis.delete(lock_key)`. TTL 은 워커 장애 안전망.

### 6-5. 동적 스케줄링 (`next_scrape_at`)

```python
def _calc_next_scrape_at(shipment, now) -> datetime | None:
    status = (shipment.status or "").lower()

    if status in ("delivered", "stopped"):
        return None                              # 종료

    if status == "arrived":
        return now + timedelta(hours=3)

    # tracking
    if shipment.eta and (shipment.eta - now) <= timedelta(days=3):
        return now + timedelta(hours=6)          # ETA 임박
    return now + timedelta(hours=12)             # 기본
```

### 6-6. 에러 처리

- 개별 shipment 실패는 **다른 shipment 에 전파 금지** (loop continue)
- Task 전체는 1시간 Beat 재실행에 의존 (자연 재시도)
- 치명적 재시도 필요하면 `@celery.task(autoretry_for=..., retry_kwargs=...)` 데코레이터 명시

---

## 7. 스크래핑 결과 저장 (scraping 레포가 호출)

scraping 레포의 `save_tracking_result(result)` 흐름:

1. MBL 로 기존 shipment 조회 — 없으면 ValueError (tracking-api POST /ocean/shipments 가 단독 생성자)
2. shipment 헤더 필드 UPDATE (carrier/status/ETA 등)
3. `ocean_containers` **UPDATE 기반 upsert** by `(shipment_id, number)` — UPDATE 존재, INSERT 신규, 응답에 없는 것은 그대로 유지
4. `ocean_container_events` **append-only + dedup** by `(container_id, timestamp, location_id, description)` + DB-level `UNIQUE(team_id, container_id, event_hash)` — 이벤트는 누적됨
5. `ocean_scrape_logs` INSERT (이번 스크랩의 raw JSON 보존)
6. scraping 워커가 Redis 락 해제

**하드 삭제/DELETE는 이 흐름에 없음.** `next_scrape_at` 은 tracking-api 의 Celery Beat 가 `_calc_next_scrape_at` 로 관리 (스크래핑은 건드리지 않음).

---

## 8. PR 리뷰 체크리스트 (복합 도메인 고유)

- [ ] 테이블 이름 `<domain>_*` prefix
- [ ] 모델 클래스는 prefix 없이 (`ShipmentModel`, `ContainerModel`)
- [ ] 서브리소스 router prefix 가 부모 path 아래 중첩
- [ ] 라인 테이블 `__with_team_rel__ = False`
- [ ] 자식 FK 는 `ForeignKeyConstraint(["team_id", "parent_id"], ...)`
- [ ] 헤더 relationship `primaryjoin` 에 team_id + parent_id 매칭
- [ ] Celery task 는 sync session + Raw Core (시스템 모드)
- [ ] Celery task `imports=[...]` 에 등록
- [ ] Redis 분산 락 + send_task 실패 시 락 해제
- [ ] 즉시 디스패치 라우터만 `await db.commit()` 허용 (이중 commit)
- [ ] `next_scrape_at` 상태별 계산, `delivered`/`stopped` 는 NULL
- [ ] 표준 도메인 규약 (`src/team/CLAUDE.md`) 전반 따름
