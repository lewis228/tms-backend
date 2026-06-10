# CLAUDE.md — TMS Pro Backend (`backend_tms-api`)

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **이 레포는 무엇인가.** TMS Pro (Transportation Management System) 백엔드 API 서버. FastAPI + Async SQLAlchemy + Celery + Redis + MinIO 스택. STE Tracking 백엔드 (`ste/backend_tracking-api`) 의 코드베이스를 그대로 복사한 후 컨테이너 운송 비즈니스에 맞춰 도메인을 확장한 형태. **ste 패턴이 헌법이다.**
>
> **새 도메인을 만들 때 — `src/team/CLAUDE.md` (표준 도메인) 와 `src/delivery_order/CLAUDE.md` (TMS 대표 도메인 + state machine) 를 먼저 읽고 시작한다.**

---

## ⭐ 가장 중요한 원칙 — Team이 멀티테넌시 루트

> **모든 비즈니스 데이터는 팀(Team)을 기점으로 존재한다.** `User`, `Team`, `UserTeam` 조인, `PermissionModel` 마스터, `FileAssetModel` 폴리모픽 — 이 네 가지만 예외고 나머지는 전부 `team_id` 를 갖는다. 팀이 삭제되면 그 팀 소유의 D/O / Container / Leg / Settlement / Driver / Truck / Customer 등 전부 CASCADE 로 물리 삭제된다.
>
> 크로스 테넌시 누출은 **3단 방어선**으로 차단:
> 1. **DB**: `TeamScopedMixin` 이 주입한 `team_id FK → teams.id ondelete=CASCADE` + 같은 도메인 내부 라인은 복합 FK `(team_id, parent_id)` + `UniqueConstraint("team_id", "id")`
> 2. **ORM**: 모든 relationship 의 `primaryjoin` 에 `foreign(X.team_id) == Y.team_id` 포함
> 3. **App**: Repository `TeamScopedRepoMixin._require_team()` + Router `Depends(get_team_scope)`
>
> **새 모델/레포/라우터를 만들 때 이 3단 방어선을 모두 세워라.** 세부 규약은 `src/team/CLAUDE.md` (표준 도메인 레퍼런스) 와 `src/delivery_order/CLAUDE.md` (헤더 + 라인 + state machine) 참조.

---

## Sub-CLAUDE.md 네비게이션

| 경로 | 역할 |
| --- | --- |
| `src/CLAUDE.md` | 도메인 트리, 의존 방향, 의존 규칙, 새 도메인 어디에 둘지 결정 트리 |
| `src/common/CLAUDE.md` | 예외, 미들웨어, Settings, Base model, 공통 스키마, lifecycle, DB / Redis / MinIO 의존 |
| `src/common/pagination/CLAUDE.md` | ⭐ MANDATORY — 커서 페이징 규약 + DELETE 응답 표준 + WS entity event + /sync |
| `src/common/repository/CLAUDE.md` | ⭐ `TeamScopedRepoMixin` — Repository 작성 규약 |
| `src/auth/CLAUDE.md` | JWT + API Key 통합 인증, `access_token` / `permission_guard`, OAuth, OTP, **driver phone+OTP 추가 가이드** |
| `src/team/CLAUDE.md` | ⭐ **표준 도메인 레퍼런스** — 새 도메인 만들 때 이 구조 복제 |
| `src/rbac/CLAUDE.md` | 권한 모델, 권한 코드, `permission_guard`, **RolesEnum + role 가드** (driver / dispatcher / admin) |
| `src/delivery_order/CLAUDE.md` | ⭐ **TMS 대표 도메인** — 헤더 / 라인 (container) 분리 + state_machine.py 패턴 |
| `src/driver_mobile/CLAUDE.md` | ⭐ **BFF 도메인** — model/repo 없이 다른 도메인 service 조립. driver 모바일 앱 진입점. **flutter_driver_app 작업 직전 필독** |

---

## Project Overview

TMS Pro Backend — 컨테이너 운송 / 항만 / 트럭 디스패치 워크플로우 관리.

핵심 비즈니스 도메인:
- **D/O (Delivery Order)** — 헤더 (`delivery_order/`) + 컨테이너 (`container/`, =Shipment) 분리. PLANNING → DISPATCHING → DISPATCHED → YARD_STAGED → FINAL_DELIVERY → EMPTY_STAGED → COMPLETED. 상태는 leg 기준 파생 + Hold/Cancel overlay.
- **Leg** — 트럭 한 대가 한 컨테이너로 한 구간. PENDING → ASSIGNED → IN_TRANSIT → COMPLETED/FAILED, DRY_RUN(빠꾸→reissue). `load_type_template` 로 자동생성.
- **요율 (재설계 Zone×Zone)** — `rate_group`(method ZONE/CITY/MILE/HOURLY) + `rate_sheet`(슬롯 = group×move×service) / `rate_entry`(from→to zone/city 셀, 유효일자 버전관리) + `rate_zone`/`rate_multiplier` + `driver_rate_assignment`. `RateResolver` 가 from_zip→from_zone, dest_zip→to_zone 으로 해석. (rate_point 폐기)
- **정산 · 청구 (재설계)** — `payroll`(드라이버 정산, leg base snapshot) + `invoice`(고객 청구, cost-plus 원가프리필+마진).
- **Driver / Truck / Chassis** — 운송 자원 마스터. driver 는 모바일 앱 사용자.
- **Street Turn / Dual Transaction** — 컨테이너 직접 이전 / 반납+픽업 묶음.
- **Realtime / Audit** — WebSocket 푸시 + Notification + location ping + 활동 타임라인(`audit_log`).

---

## Development Commands

```bash
# 인프라만
docker-compose -f docker-compose.local.yaml up -d mysql redis minio minio-init

# 전체 (앱 포함)
docker-compose -f docker-compose.local.yaml up -d

# 로컬 앱 (로컬 디버깅)
PYTHONPATH=src uvicorn main:app --host 0.0.0.0 --port 8080 --app-dir src --reload

# 마이그레이션
alembic upgrade head
alembic revision --autogenerate -m "description"

# 테스트
PYTHONPATH=src pytest tests/ -v
PYTHONPATH=src pytest tests/path/to/test_file.py::test_specific -v

# Celery (Phase D 활성화 후)
cd src && PYTHONPATH=. celery -A celery_app worker --loglevel=info
cd src && PYTHONPATH=. celery -A celery_app beat --loglevel=info
```

---

## Architecture — 고수준 개요

### Module Pattern (DDD)

모든 도메인은 `src/<domain>/` 아래에:
- `model.py` — SQLAlchemy (`Base, TeamScopedMixin` 이중 상속이 기본)
- `repository.py` — `TeamScopedRepoMixin` 상속
- `service.py` — `__init__(db, team_id)` 시그니처
- `router.py` — `Depends(get_team_scope)` 주입
- `schemas/` — Pydantic (`RequestSchema` / `ResponseSchema` 상속)
- `const/`, `dependencies/` — 필요 시
- `state_machine.py` — 상태 전이가 있는 도메인만 (delivery_order, leg)

세부: `src/team/CLAUDE.md`. 헤더+라인 분리 도메인은 `src/delivery_order/CLAUDE.md`. BFF 패턴 (모델 없음) 은 `src/driver_mobile/CLAUDE.md`.

### 팀 스코프 요청 흐름 (TMS 패턴)

```
1. HTTP Request (X-API-Key 또는 Authorization: Bearer)
2. AuthMiddleware (JWT 디코드 — 실패해도 raise 안 함)
3. access_token        → token_type == "access" 검증
4. permission_guard(X) → RBAC 코드 보유 검사 (필요 시)
5. get_team_scope      → X-Team-Id 헤더 검증 (user_teams 멤버십)
6. get_current_user    → request.state.user → UserResponseSchema
7. ServiceClass(db, team_id)  → Repository 생성자까지 team_id 전파
8. Repository._require_team() → 모든 쿼리 WHERE 첫 조건
```

> ⚠️ **STE 와 다른 점**: ste 는 `auth: AuthResult = Depends(jwt_or_api_key)` 한 줄로 처리. tms 는 `_1: None = Depends(access_token)` + `_2: None = Depends(permission_guard(...))` 명시적 분리. 결과 객체를 안 받아도 dependency 가 raise 함. 세부 규약은 `src/team/CLAUDE.md` §2-3.

### Middleware Stack (`main.py` 역순 등록)

1. CORSMiddleware (최외곽)
2. LogContextMiddleware (`X-Request-ID` 주입)
3. AuthMiddleware (JWT 디코드, 실패해도 raise 안 함)
4. AccessLogMiddleware (method/path/status/ms)

### Database

- Async MySQL (SQLAlchemy 2.0 + aiomysql)
- Read/write split: `get_read_db()` / `get_write_db()`
- Base model: `id`, `is_active`, `created_at`, `updated_at`, `created_by_user_id`, `updated_by_user_id`
- **Soft delete 원칙**, 하드 삭제는 FK CASCADE (팀/부모 삭제) 트리거 시에만
- Query timeout: read 30초, write 600초 (`database/timed_session.py`)
- **DateTime 은 항상 UTC** (`DateTime(timezone=True)`)

### Infrastructure

- Redis: 세션 / 캐시 / OTP / WebSocket pub/sub (`cache/`, read/write split)
- MinIO/S3: 파일 (`file/`)
- Logging: structlog + request_id (`common/logging/`)
- Pagination: **커서 기반만** (`common/pagination/`)
- WebSocket: `realtime/` (id-only payload + /sync events 배열)

---

## Adding a New Domain Module

1. `src/<domain>/` 생성 — `src/team/CLAUDE.md` 구조 복제
2. `model.py` — **반드시** `(Base, TeamScopedMixin)` 이중 상속 (시스템/글로벌 모델 제외)
3. `repository.py` — **반드시** `TeamScopedRepoMixin` 상속
4. `service.py` — `__init__(self, db, team_id)` 시그니처
5. `router.py` — `Depends(access_token)` + `Depends(permission_guard(...))` + `Depends(get_team_scope)` 조합
6. `schemas/request.py`, `schemas/response.py`
7. 모델을 `src/common/model/models_registry.py` 에 import 등록
8. 라우터를 `src/main.py` 에 `include_router`
9. `alembic revision --autogenerate -m "add <domain>"` → migration 확인 → `alembic upgrade head`
10. 파일 업로드 필요하면 `src/file/const/domains.py` 추가
11. 권한이 필요하면 `src/rbac/const/const.py` 에 코드 추가 + `DEFAULT_*_CODES` 매핑
12. WebSocket entity event 필요하면 service mutation 메서드 끝에 `publish_entity_event(redis, team_id, "<domain>.<action>", entity)` 호출
13. 모바일 노출 필요하면 `src/driver_mobile/router.py` 에 BFF 엔드포인트 추가 (model/repo 만들지 말 것)

복합 도메인 (헤더 + 라인 + state machine) 이면 `src/delivery_order/CLAUDE.md` 패턴 따름.

---

## TMS Pro 비즈니스 컨텍스트

### 도메인 모듈 분류

**팀 scoped — 비즈니스 (TeamScopedMixin 상속)**:

| 카테고리 | 도메인 |
| --- | --- |
| Master Data | `customer`, `terminal`, `vessel`, `location`, `driver`, `truck`, `equipment_pool`, `chassis` |
| D/O Workflow | `delivery_order`, `container`, `container_stop`, `chassis_event`, `street_turn`, `dual_transaction` |
| Leg / Dispatch | `leg`, `leg_layer`, `leg_driver_segment`, `load_type_template` |
| Rate (재설계 Zone×Zone) | `rate_zone`, `rate_group`, `rate_sheet`, `rate_multiplier`, `driver_rate_assignment`, `addon`, `rate_import` |
| 정산 · 청구 (재설계) | `payroll`, `invoice`, `audit_log` |
| Mobile / Realtime | `location_ping`, `push_token`, `notification`, `realtime`, `driver_mobile` (BFF) |
| AI / Analytics | `ai_intake`, `analytics` |
| API | `api_key` (외부 개발자 통합) |

**팀 미소속 (TeamScopedMixin 예외 — 글로벌 마스터)**:
- `user` — 전역 (한 유저가 여러 팀 소속 가능)
- `team` — 자신이 루트
- `file` — 폴리모픽 (`domain` + `object_id` 로 소유 연결)
- `rbac/permissions` — 전역 권한 코드 카탈로그

### DB 스키마 — 팀 스코프 관점

모든 팀 scoped 테이블은 다음 규약 공통:
- `team_id` 컬럼 NOT NULL + `FK → teams.id ondelete=CASCADE`
- `UniqueConstraint("team_id", "id")` (복합 FK 타겟용)
- 모든 인덱스 `team_id` leftmost
- **같은 도메인 내부** 라인 테이블은 `ForeignKeyConstraint(["team_id", "parent_id"], ...)` 복합 FK (예: `container.delivery_order_id` → `delivery_order.(team_id, id)`)
- **도메인 간 FK** (예: `delivery_order.customer_id`) 는 단순 FK + `ondelete` 분기 (`RESTRICT` / `SET NULL` / `CASCADE` 비즈니스 의미별)

### 상태 전이 도메인 (state machine)

| 도메인 | 파일 | 상태 |
| --- | --- | --- |
| `delivery_order` | `delivery_order/state_machine.py` + `state_derive.py` | PLANNING → DISPATCHING(파생) → DISPATCHED → YARD_STAGED → FINAL_DELIVERY → EMPTY_STAGED → COMPLETED (+Hold/Cancel overlay) |
| `leg` | `leg/state_machine.py` | PENDING → ASSIGNED → IN_TRANSIT → COMPLETED / FAILED, DRY_RUN |
| `payroll` | `payroll/service.py` | DRAFT → CONFIRMED → PAID / VOID |
| `invoice` | `invoice/state_machine.py` | DRAFT → ISSUED → PAID / VOID |
| `street_turn` | (status enum + service 검증) | REQUESTED → APPROVED / REJECTED / CANCELLED |

상태 전이는 반드시 `state_machine.py` 또는 service 안의 단일 함수 (`_assert_can_transition`) 통과. UI 레이어에서 임의 status 업데이트 금지.

세부: `src/delivery_order/CLAUDE.md`.

### Driver 모바일 앱

`driver_mobile/` 도메인은 **BFF (Backend for Frontend)** — 자체 model/repository 없음. 다른 도메인 (`leg`, `driver`, `location_ping`, `push_token`) 의 service 를 호출해 모바일 친화 응답으로 조립.

- **모든 엔드포인트가 `require_driver` 가드** 통과 (`role == DRIVER`)
- 인증: 폰번호 + OTP (`auth/router.py` 의 OTP 흐름 — driver 용 케이스 추가)
- 라우터 prefix: `/api/v1/driver/...`
- 핵심: `tasks/today` (오늘 할 일), `legs/{id}/checkpoint` (상태 전이), `location/batch` (위치 배치 업로드), `legs/{id}/stops/{stop_id}/arrive|depart` (도착/출발 보고)

세부: `src/driver_mobile/CLAUDE.md`.

### 전역 삭제 정책 (통일)

| 케이스 | 방식 |
| --- | --- |
| 사용자 삭제 요청 | Soft (`is_active=False`) |
| 팀/헤더 삭제 → 하위 | Hard CASCADE (DB 레벨 자동) |
| API Key 회수 | Soft (`is_active=False`) — `updated_at` 이 회수 시점 |
| 운송 이벤트 (chassis_event, location_ping) | Append-only — 삭제 없음 |

**하드 삭제는 오직 DB CASCADE 가 트리거할 때만.** 애플리케이션 레벨에선 전부 soft. `revoked_at` 같은 별도 컬럼은 쓰지 않고 `is_active` 하나로 통일.

### Soft-delete 직후 응답 — DELETE 200 + entity

```python
@router.delete("/{do_id}", response_model=DeliveryOrderResponseSchema)
async def delete_do(do_id: int, ...):
    return await svc.delete(do_id, updater_user_id=me.id)
```

Service:
```python
async def delete(self, do_id: int, *, updater_user_id: int) -> DeliveryOrderResponseSchema:
    obj = await self.repo.get(do_id)
    if not obj: raise NotFoundException("DeliveryOrder")
    obj.is_active = False
    obj.updated_by_user_id = updater_user_id
    await self.db.flush()
    await self.db.refresh(obj)        # PK SELECT — is_active 필터 무관
    return DeliveryOrderResponseSchema.model_validate(obj)
```

WHY: 프론트가 `setQueryData` 로 즉시 캐시 패치 가능. 세부: `src/common/pagination/CLAUDE.md` §"DELETE 응답 표준".

### WebSocket Entity Event (id-only)

CUD 작업 후:
```python
from common.events.entity_publisher import publish_entity_event

await publish_entity_event(
    redis, self.team_id, "delivery_order.created", entity,
)
```

payload:
```json
{
  "type": "delivery_order.created",
  "team_id": 1,
  "timestamp": "2026-05-12T10:00:00Z",
  "payload": {"id": 123, "team_id": 1}
}
```

클라이언트 (web/mobile) 가 id 만 받아 `GET /<domain>/{id}` 호출 후 캐시 패치. 세부: `src/common/pagination/CLAUDE.md` §"WebSocket entity 이벤트".

### Sync Delta — `GET /<domain>/sync?since=<ts>`

WebSocket reconnect 후 누락된 변경 catch-up. events 배열 응답 (WS 와 동일 shape):

```json
{
  "events": [
    {"event": "delivery_order.updated", "id": 50},
    {"event": "delivery_order.deleted", "id": 100}
  ],
  "all_ids": null,
  "meta": {"count": 2, "sync_time": "2026-05-12T10:05:00Z"}
}
```

세부: `src/common/pagination/CLAUDE.md` §"Sync delta 엔드포인트".

---

## TMS specific 결정 (ste 와 다른 점)

| 영역 | ste | tms | 이유 |
| --- | --- | --- | --- |
| 인증 가드 | `auth: AuthResult = Depends(jwt_or_api_key)` 한 줄 | `_1: None = Depends(access_token)` + `_2: None = Depends(permission_guard(...))` 분리 | 권한 가드 활성 사용 + 외부 API Key 호출자가 거의 없음 (대부분 admin/dispatcher 인증) |
| `permission_guard` | 정의만, 미사용 | 활성 사용 (`DO_WRITE`, `LEG_WRITE` 등 코드 부착) | TMS 운영 — admin / dispatcher / driver / customer 역할 구분 필요 |
| `rate_limit` | 모든 엔드포인트 부착 | 미부착 (현재) | 외부 API 호출자가 적음. 추후 external API 노출 시 부착 |
| `RolesEnum` | 없음 (permission code 만) | `RolesEnum.{ADMIN, DISPATCHER, DRIVER, CUSTOMER, ...}` 도입 | 모바일 앱이 driver 전용 — role 단위 가드 (`require_driver`) 필요 |
| State Machine | 없음 | `delivery_order/state_machine.py` 등 별도 파일 | 트랜잭션 상태 전이가 핵심 비즈니스 — 검증 로직 응집 |
| `service_v3.py` | 없음 | `driver_mobile/service_v3.py` 같은 점진 마이그레이션 흔적 | v2 → v3 호환 유지 |
| BFF 도메인 | 없음 | `driver_mobile/` (model/repo 없음, router + service 만) | 모바일 앱 친화 응답 형태 (다른 도메인 조립) |
| Enum 직렬화 | 주로 `String` + 검증 | `SAEnum` (DB 레벨 enum) | 상태값이 명확하고 변동 적음 |
| 도메인 간 FK | 같은 도메인 안 라인은 복합 FK | 도메인 간은 단순 FK + ondelete 분기 (`RESTRICT` / `SET NULL` / `CASCADE`) | 비즈니스 의미별 보호 — customer 삭제 시 D/O 보존 (RESTRICT), vessel 삭제 시 D/O 의 vessel_id NULL (SET NULL) |
| Celery 사용 빈도 | 핵심 (스크래핑 큐) | 옵션 (ai_intake / notification dispatch / push) | 동기 워크플로우 위주 |

---

## 절대 하지 말 것 (전역 안티 패턴)

| 안티 패턴 | 대안 | 이유 |
| --- | --- | --- |
| `(Base, TeamScopedMixin)` 안 한 모델 | 무조건 상속 (글로벌 마스터 제외) | 멀티테넌시 누출 |
| `team_id` WHERE 절 빠뜨림 | `Model.team_id == self._require_team()` 첫 조건 | 누출 |
| `ondelete=CASCADE` 누락 | team_id FK 는 항상 CASCADE | 팀 삭제 시 orphan |
| `commit()` 호출 | `flush()` + dependency 가 자동 commit | 트랜잭션 경계 깨짐 |
| `find_*` 메서드명 | 전부 `get_*` / `list_*` | 컨벤션 |
| `LIMIT/OFFSET` 페이징 | `CommonService.paginate()` | 커서 기반 강제 |
| 라우터에서 `model_validate` | service 가 Pydantic 반환 | 책임 분리 |
| 라우터에서 `try/except` | 전역 핸들러로 전파 | 일관 포맷 |
| `print()` | `logger.info(...)` (structlog) | 구조화 로깅 |
| 사용자 노출 메시지 한국어 하드코딩 | `AppException(code=..., message=...)` 코드 + 메시지 | 향후 i18n / 클라이언트 로컬라이즈 |
| `permission_guard` 우회 (라우터에 권한 가드 안 붙임) | 모든 mutation 라우터에 부착 | RBAC 적용 |
| `state_machine` 우회 (status 직접 UPDATE) | `assert_can_transition` 통과 후 | 비즈니스 룰 위반 |
| `driver_mobile/` 안에 model/repo 만들기 | 다른 도메인의 service 호출 (BFF 패턴 유지) | 도메인 분리 |

---

## Onboarding

새 멤버:
1. 이 파일 (루트 CLAUDE.md) 읽기
2. `src/CLAUDE.md` — 도메인 트리 + 의존 방향
3. `src/common/CLAUDE.md` — 공통 인프라 (Base, TeamScopedMixin, exceptions, schemas)
4. `src/team/CLAUDE.md` — **표준 도메인 (model/repo/service/router/schemas) 작성 규칙**
5. `src/common/pagination/CLAUDE.md` — 페이징 + DELETE + WS + /sync
6. `src/common/repository/CLAUDE.md` — TeamScopedRepoMixin
7. `src/auth/CLAUDE.md` — 가드 종류 + JWT/세션
8. `src/rbac/CLAUDE.md` — 권한 코드 + role 가드
9. `src/delivery_order/CLAUDE.md` — TMS 대표 도메인 (state machine + 헤더/라인)
10. `src/driver_mobile/CLAUDE.md` — BFF + 모바일 라우팅

새 도메인 만들 때: 위 4 + 7 + 9 면 충분.
모바일 엔드포인트 추가할 때: 10 만 보면 됨.
