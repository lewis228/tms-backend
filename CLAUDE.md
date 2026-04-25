# CLAUDE.md — TMS Pro Backend

> Claude Code 가 이 백엔드 레포에서 작업할 때 따라야 할 단일 진실(SoT). 모든 도메인·계층 규칙을 이 문서 하나에 모은다. 하위 폴더에 별도 CLAUDE.md 없음.

---

## 🧭 정체성

- **TMS Pro** = 컨테이너 드레이지(Drayage) 배차 관리 SaaS
- 한 시스템에 4 역할: `SUPER_ADMIN`, `ADMIN`, `DISPATCHER`, `DRIVER`
- DRIVER 는 모바일 앱(Flutter, 별도 레포)을 사용한다. 본 백엔드는 **웹 + 모바일** 양쪽 API 를 모두 제공한다.
- ⭐ ste(`backend_tracking-api`) 와 **다른 멀티테넌시 모델**: 사용자 N : 1 Tenant. 한 사용자는 한 회사(테넌트)에만 속한다. `UserTeam` 같은 조인 테이블 없음.

---

## ⭐ 가장 중요한 원칙 — Tenant 가 멀티테넌시 루트

> **모든 도메인 데이터는 Tenant 를 기점으로 존재한다.** `User`, `Tenant`, `File`(폴리모픽 첨부), `RatePolicy`(시스템 마스터)만 예외이고, 그 외 도메인 모델은 전부 `tenant_id` NOT NULL 컬럼을 갖는다. Tenant 가 삭제되면 그 Tenant 소유의 모든 행이 CASCADE 로 정리된다.
>
> 크로스 테넌시 누출은 **3단 방어선**으로 차단:
> 1. **DB**: `TenantAuditMixin` 이 주입한 `tenant_id` + `FK → tenants.id ondelete=CASCADE` + 모든 인덱스에 `tenant_id` leftmost
> 2. **Repository**: `BaseRepository[ModelT]` 가 모든 쿼리에 `WHERE tenant_id = self.tenant_id AND is_deleted = False` 자동 주입
> 3. **App**: 모든 라우터는 `Depends(CurrentUser)` + `Depends(TenantID)` 로 진입. 서비스 인스턴스화 시 `tenant_id` 를 주입 (`XxxService(XxxRepository(db, tenant_id=tenant_id), tenant_id)`)
>
> **새 도메인을 만들 때 이 3단 방어선을 모두 세워라. 검사 없이 생 SQL/생 Session.execute 사용 금지.**

### Tenant 컨텍스트 결정 로직

- 일반 사용자 (ADMIN / DISPATCHER / DRIVER) → JWT 의 `tenant_id` 클레임 사용
- SUPER_ADMIN → JWT 의 `tenant_id` 가 비어있을 수 있고, 요청 시 `X-Tenant-ID` 헤더로 작업 대상 tenant 지정
- 일반 사용자가 `X-Tenant-ID` 를 보내도 **JWT 의 tenant_id 와 다르면 거부 (403)**
- `app/core/middleware.py:TenantContextMiddleware` 가 `tenant_id_ctx` ContextVar 에 결정된 값을 저장 → 로그·repository 에 자동 주입

---

## 🏗 디렉토리 구조 (flat — nested 절대 금지)

```
backend_tms-api/
├── app/
│   ├── main.py                      # FastAPI 팩토리, lifespan, 라우터 등록
│   ├── config.py                    # pydantic-settings (Settings)
│   ├── core/                        # 도메인 무관 인프라
│   │   ├── database.py              # write/replica 엔진, get_db / get_db_replica
│   │   ├── dependencies.py          # DB / DBReadOnly / CurrentUser / TenantID / require_role
│   │   ├── security.py              # bcrypt + JWT + temp password
│   │   ├── exceptions.py            # TMSException 계층 + handlers
│   │   ├── middleware.py            # RequestLoggingMiddleware, TenantContextMiddleware
│   │   ├── logging.py               # structlog + PII 마스킹
│   │   ├── pagination.py            # PageParams, PagedResponse[T]
│   │   ├── repository.py            # BaseRepository[ModelT] (tenant 자동 필터)
│   │   ├── schema.py                # BaseSchema (camelCase alias, from_attributes)
│   │   └── redis.py                 # 싱글턴 async redis client
│   ├── models/
│   │   ├── base.py                  # UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin,
│   │   │                            # TenantMixin, AuditMixin, TenantAuditMixin
│   │   ├── enums.py                 # UserRole, DeliveryStatus, LegStatus 등
│   │   └── models_registry.py       # Phase 1: 모든 도메인 모델 import (Alembic autogenerate 보장)
│   ├── api/
│   │   └── health.py                # GET /health
│   ├── domains/                     # ⭐ 18 도메인 — 각각 7파일
│   │   ├── auth/
│   │   ├── tenants/
│   │   ├── users/
│   │   ├── drivers/
│   │   ├── customers/
│   │   ├── terminals/
│   │   ├── vessels/
│   │   ├── locations/
│   │   ├── delivery_orders/
│   │   ├── legs/
│   │   ├── street_turns/
│   │   ├── rate_settings/
│   │   ├── settlements/
│   │   ├── files/
│   │   ├── notifications/
│   │   ├── realtime/
│   │   ├── ai_intake/
│   │   └── driver/                  # 모바일 앱 전용 엔드포인트 묶음
│   └── workers/
│       ├── celery_app.py
│       └── tasks/
├── alembic/
│   ├── env.py                       # async + Base.metadata
│   └── versions/
├── tests/
│   └── <domain>/                    # 도메인별로 unit + integration 섞어서
├── _archive_ste/                    # ste 에서 살릴 코드 임시 보관 (gitignore). Phase 1 종료 후 삭제
├── pyproject.toml
├── alembic.ini
├── Dockerfile
├── docker-compose.local.yaml
├── docker-compose.prod.yaml
├── .env / .env.example / .envrc
├── .gitignore / .dockerignore
└── CLAUDE.md (this file)
```

### ⛔ 금지 패턴
- ste 가 사용한 nested 도메인 구조 (`src/ocean/container/...`) 절대 금지. **모든 도메인은 `app/domains/<single_name>/` 한 단계만**.
- `src/` 폴더 사용 금지. 진입점은 `app/`.
- 도메인 안에 별도 `schemas/`, `dependencies/`, `const/` 서브폴더 만들지 말 것 — 단일 파일 7개로 끝낸다.

---

## 📦 도메인 표준 파일 7종

각 도메인은 **반드시** 다음 7파일로 구성된다. 빈 파일이라도 둔다 (일관성).

```
app/domains/<domain>/
├── __init__.py
├── models.py            # SQLAlchemy ORM (TenantAuditMixin 상속이 기본)
├── repository.py        # BaseRepository[ModelT] 상속
├── service.py           # 비즈니스 로직. __init__(self, repo, tenant_id)
├── router.py            # APIRouter, Depends(CurrentUser, TenantID, require_role(...))
├── schema.py            # Pydantic Request/Response (BaseSchema 상속)
├── dependencies.py      # ValidXxx / ValidXxxRO 의존성
└── constants.py         # 도메인 상수, Enum 보조
```

### 작성 순서 (새 도메인 추가 시)
1. `models.py` — `TenantAuditMixin` 상속, FK / 인덱스 / UniqueConstraint 작성
2. `app/models/models_registry.py` 에 import 추가 (Alembic 이 모델을 인식하도록)
3. `schema.py` — Request / Response 작성, camelCase alias
4. `repository.py` — `BaseRepository[ModelT]` 상속, 도메인 특수 쿼리 추가
5. `service.py` — `__init__(self, repo: XxxRepository, tenant_id: str)`
6. `dependencies.py` — `ValidXxx` (쓰기 시 path param 검증), `ValidXxxRO` (읽기)
7. `router.py` — `APIRouter(prefix="/api/v1/<domain>", tags=[...])`
8. `app/main.py` 의 `create_app()` 안에서 `app.include_router(...)`
9. `alembic revision --autogenerate -m "add <domain>"` → 마이그레이션 검토 → `alembic upgrade head`

### 서비스 생성 패턴 (router 안에서)
```python
def _svc(db: AsyncSession, tenant_id: str) -> XxxService:
    return XxxService(XxxRepository(db, tenant_id=tenant_id), tenant_id)
```

### DB 세션 컨벤션
- GET 엔드포인트 → `DBReadOnly`, `ValidXxxRO` 사용 (read replica)
- 쓰기 엔드포인트 → `DB`, `ValidXxx` 사용 (write primary)
- 같은 요청에서 `ValidXxx` 와 `db: DB` 를 공유하면 FastAPI Depends 캐싱으로 동일 세션 보장

---

## 🔐 인증·권한

- **JWT (HS256)**: access 60분, refresh 30일. claim: `sub`(user_id), `tenant_id`, `role`, `exp`, `iat`
- **Bcrypt** 비밀번호 해싱 (cost 12)
- **Driver 계정 생성** 시 `secrets` 모듈로 임시 비밀번호 발급. 응답에 1회 노출 후 DB 에는 해시만 저장. 첫 로그인 시 강제 변경.
- **역할 계층 (`_ROLE_RANK`)**:
  ```
  DRIVER: 0  →  DISPATCHER: 1  →  ADMIN: 2  →  SUPER_ADMIN: 3
  ```
  - 사용자는 자신과 같거나 낮은 등급만 생성/수정 가능
  - SUPER_ADMIN 은 API 로 생성 불가 (CLI 또는 마이그레이션 시드)
  - `CUSTOMER` 역할은 v2 (Customer Portal). 현재 미사용
- **`require_role(*roles)`**: `app/core/dependencies.py` 의 데코레이터 팩토리. 라우터의 `dependencies=[]` 에 사용

---

## 🌐 미들웨어 등록 순서

`app/main.py:create_app()` 에서 **역순으로 add_middleware**:

1. `CORSMiddleware` (가장 바깥)
2. `RequestLoggingMiddleware` (request_id 생성, 처리 시간)
3. `TenantContextMiddleware` (JWT/`X-Tenant-ID` 결정 → ContextVar)

---

## 🛢 데이터베이스

- MySQL 8.4 + SQLAlchemy 2.0 async + aiomysql
- Read/Write 분리: `database_url` (write) / `database_replica_url` (read). replica 미설정 시 write 풀 공유
- 풀 설정: `pool_pre_ping=True`, `pool_use_lifo=True`, `pool_recycle=3600`
- **모든 모델은 `TenantAuditMixin` 상속이 기본** (UUID PK + 타임스탬프 + soft delete + tenant_id)
- `is_deleted` 플래그로 소프트 삭제. 하드 삭제는 오직 DB CASCADE 만
- 모든 인덱스에 `tenant_id` 가 leftmost 컬럼이어야 한다

### 주요 Mixin (`app/models/base.py`)

| Mixin | 역할 |
| --- | --- |
| `UUIDPrimaryKeyMixin` | `id: str` (CHAR(36) UUID4) |
| `TimestampMixin` | `created_at`, `updated_at` (자동 갱신) |
| `SoftDeleteMixin` | `is_deleted: bool` |
| `TenantMixin` | `tenant_id: str` + FK 제약 |
| `AuditMixin` | UUID + Timestamp + SoftDelete |
| `TenantAuditMixin` | Audit + Tenant **(도메인 표준)** |

---

## 🎯 핵심 비즈니스 도메인 규약

### 도메인 매핑 (요구사항 → 18 도메인)

| 도메인 | 라우터 prefix | 핵심 모델 | 권한 |
| --- | --- | --- | --- |
| `auth/` | `/api/v1/auth` | (없음) | 공개 |
| `tenants/` | `/api/v1/tenants` | `Tenant`, `TenantSettings` | SUPER_ADMIN (CRUD), 본인 GET `/me` 는 인증 사용자 |
| `users/` | `/api/v1/users` | `User` | ADMIN+ (본인 `/me` 는 인증 사용자) |
| `drivers/` | `/api/v1/drivers` | `Driver` | DISPATCHER+ |
| `customers/` | `/api/v1/customers` | `Customer` | DISPATCHER+ (조회) / ADMIN+ (수정) |
| `terminals/` | `/api/v1/terminals` | `Terminal` | DISPATCHER+ / ADMIN+ |
| `vessels/` | `/api/v1/vessels` | `Vessel` | DISPATCHER+ |
| `locations/` | `/api/v1/locations` | `Location` (Yard, CustomerAddr) | DISPATCHER+ |
| `delivery_orders/` | `/api/v1/delivery-orders` | `DeliveryOrder` | DISPATCHER+ |
| `legs/` | `/api/v1/legs` | `Leg` (Movement + LegAssignment 통합) | DISPATCHER+ |
| `street_turns/` | `/api/v1/street-turns` | `StreetTurn` | DISPATCHER+ |
| `rate_settings/` | `/api/v1/rate-settings` | `RateSetting` | ADMIN+ |
| `settlements/` | `/api/v1/settlements` | `Settlement`, `ExtraCharge`, `SettlementAuditLog` | DISPATCHER+ (조회/계산/수정), ADMIN+ (Unapprove) |
| `files/` | `/api/v1/files` | `File` (폴리모픽: domain + object_id) | 인증 사용자 |
| `notifications/` | `/api/v1/notifications` | `Notification` | 인증 사용자 |
| `realtime/` | `/api/v1/realtime` | (SSE, no model) | 인증 사용자 |
| `ai_intake/` | `/api/v1/ai-intake` | (Claude API 통합) | DISPATCHER+ |
| `driver/` | `/api/v1/driver` | (모바일 전용 엔드포인트 묶음 — 위 도메인에서 driver 시점 export) | DRIVER |

### Delivery Order 상태 머신

```
PLANNING → DISPATCHED ─┬─► YARD_STAGED ─► FINAL_DELIVERY ─┬─► EMPTY_STAGED ─► COMPLETED
                       │                                  │
                       └──► FINAL_DELIVERY ───────────────┴─► COMPLETED
```

- 게이트 조건은 `app/domains/delivery_orders/service.py:DeliveryStateMachine` 안에서만 검증
- 위반 시 `InvalidStateTransitionError` (HTTP 422)
- 상세 게이트 조건은 요구사항 문서 v3 기준 (메모리 `project_tms_backend_design.md` 참고)

### Leg 상태 머신

```
PENDING → IN_TRANSIT ─┬─► COMPLETED
                      └─► FAILED
```

- 모바일 앱이 `POST /api/v1/driver/legs/{id}/checkpoint` 로 전이를 트리거
- 체크포인트마다 GPS 좌표 + Server Time 기록

### Street Turn 사전 조건
- Import D/O `COMPLETED`
- Export D/O `DISPATCHED` (driver, delivery_location 입력 완료)
- 두 D/O 의 `container_number` 동일
- Import 또는 Export 에 이미 StreetTurn 연결된 경우 재생성 불가

### Settlement 라이프사이클
```
PENDING → CALCULATED → ADJUSTED → APPROVED
            (자동)      (사유필수)  (잠금)
```
- Approve 후 모든 금액 필드 readonly. PATCH 거부
- Unapprove 는 ADMIN+ 만. Audit Log 자동 기록

---

## 📲 모바일 (Driver App) 전용 라우터 — `domains/driver/`

본 백엔드가 모바일 앱도 서빙하므로, DRIVER 가 호출하는 엔드포인트는 한 폴더(`domains/driver/`) 에 모은다. 데이터 모델은 다른 도메인 (`legs`, `files`) 을 재사용. 라우터만 분리.

```
GET  /api/v1/driver/tasks/today              # 오늘 배정된 Leg 목록
POST /api/v1/driver/legs/{id}/checkpoint     # Arrived/Started/Finished/Failed + GPS
POST /api/v1/driver/legs/{id}/documents      # POD/Receipt 멀티파트 업로드
POST /api/v1/driver/location                 # Background GPS batch (15분 간격)
POST /api/v1/driver/push-tokens              # FCM/APNs 토큰 등록
PATCH /api/v1/driver/me/password             # 첫 로그인 비밀번호 변경
```

---

## 🔄 실시간 (`realtime/`) — SSE

- `GET /api/v1/realtime/events` (SSE)
- 인증 필요. 이벤트 채널은 tenant 별 격리 (Redis Pub/Sub key: `tms:tenant:{tenant_id}:events`)
- 이벤트 타입: `presence.joined/left/editing`, `do.status_changed`, `leg.status_changed`, `pod.uploaded`

---

## 🤖 AI Intake (`ai_intake/`) — Claude API

- PDF/이미지 업로드 → Claude API (`claude-opus-4-7` 또는 `claude-sonnet-4-6`) 로 OCR + 필드 추출
- 응답에 신뢰도(confidence) 포함. 사용자가 검토 후 저장
- API 키는 `settings.anthropic_api_key`. 비어있으면 도메인 비활성

---

## 📐 RQRS 표준

- 응답 키는 **camelCase** alias (BaseSchema 가 자동 변환)
- 에러 응답 표준: `{ "error": { "code": "ERR_NOT_FOUND", "message": "...", "details": {...} } }`
- 성공 응답: 단건 `{ ... }`, 리스트 `PagedResponse { items, total, page, size, pages }`
- 페이징은 **page-based** (`PageParams(page, size)`, 1-indexed)
- 날짜는 ISO 8601 UTC

---

## 🧪 테스트

- pytest + `asyncio_mode=auto`
- factory-boy 로 테스트 데이터 생성
- testcontainers (MySQL, Redis) 로 통합 테스트
- 디렉토리: `tests/<domain>/test_*.py` — 도메인별로 unit + integration 모음
- 커버리지 목표 80%

---

## 🛠 개발 명령

```bash
# 인프라만 (MySQL/Redis/MinIO)
docker-compose -f docker-compose.local.yaml up -d mysql redis minio minio-init

# 전체 스택
docker-compose -f docker-compose.local.yaml up -d

# 로컬 앱만 (인프라는 docker, 앱은 host venv)
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# Celery
celery -A app.workers.celery_app worker --loglevel=info -Q celery
celery -A app.workers.celery_app beat --loglevel=info

# 마이그레이션
alembic revision --autogenerate -m "add <domain>"
alembic upgrade head

# 테스트
pytest                                       # 전체
pytest tests/delivery_orders/                # 도메인별
pytest --cov=app --cov-report=term-missing   # 커버리지
```

---

## 🚫 ste 에서 가져오면 안 되는 것

이 백엔드는 ste(`backend_tracking-api`) 를 베이스로 분기했지만, 다음은 **재사용하지 않는다**:

- `src/` 진입점 구조 (이제 `app/`)
- nested 도메인 (`ocean/container`, `terminal/appointment` 등)
- `TeamScopedMixin` / `UserTeam` 조인 / `X-Team-Id` 헤더 (이제 `TenantAuditMixin` / 단일 tenant / `X-Tenant-ID` SUPER 전용)
- `permission_guard` RBAC 시스템 (이제 `require_role` 단순화)
- 커서 기반 페이징 (이제 page-based)
- `api_key/` 도메인 (TMS Pro 는 외부 API 키 발급 안 함; v2 검토)
- `cache/`, `tag/`, `carrier/`, `air/`, `rail/`, `terminal/`(ste 의), `vessel/ais` (도메인 자체가 다름)

ste 코드 중 **재사용 가능한 파일들 (oauth, smtp_sender, structlog 설정, middleware 골격, location/UN-LOCODE CSV)** 은 `_archive_ste/` 에 임시 보관됨. Phase 1 작업 시 해당 파일을 참고만 하고 새 구조에 맞춰 다시 작성한다 (그대로 import 금지).

---

## 🧷 작업할 때 항상 점검

새 코드를 만들 때 다음 체크리스트를 매번 머릿속에 돌려라:

- [ ] `tenant_id` 가 모델, 인덱스, 쿼리, 응답에 일관되게 흐르는가?
- [ ] Repository 가 `BaseRepository` 를 상속하고 있는가?
- [ ] Router 가 `Depends(CurrentUser)` + 적절한 `require_role(...)` 을 걸고 있는가?
- [ ] 응답 스키마가 `BaseSchema` 를 상속하고 camelCase 로 직렬화되는가?
- [ ] 에러 케이스에 적절한 `TMSException` 서브클래스를 raise 하는가?
- [ ] 마이그레이션을 `models_registry.py` 에 import 추가 후 생성했는가?
- [ ] FK / 인덱스 / UniqueConstraint 가 다중 테넌시 정책을 만족하는가?
- [ ] Driver 가 호출하는 엔드포인트라면 `domains/driver/` 에 라우터를 분리했는가?
- [ ] 리스트 응답이 `PagedResponse` 를 사용하는가?
- [ ] 새로운 환경변수가 `app/config.py:Settings` + `.env.example` 둘 다에 추가됐는가?
