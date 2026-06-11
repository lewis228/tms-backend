# src/CLAUDE.md — 도메인 트리 / 의존 방향 / 결정 트리

> 이 문서는 `src/` 안의 도메인 폴더 배치와 의존 방향을 정의한다. 새 파일을 만들기 전에 반드시 이 문서로 위치를 결정.

---

## 1. 전체 트리

```
src/
├── main.py                    ─ FastAPI 진입점 (lifespan + middleware + router include)
├── celery_app.py              ─ Celery worker / beat 진입점
│
├── common/                    ─ 모든 도메인이 의존하는 공통 인프라
│   ├── const/                 │  Settings, filter_mapper, path 상수
│   ├── email/                 │  SMTP 발송
│   ├── exceptions/            │  AppException + 전역 핸들러
│   ├── lifecycle/             │  FastAPI lifespan
│   ├── logging/               │  structlog 설정
│   ├── middleware/            │  CORS / Auth / LogContext / AccessLog / Session
│   ├── model/                 │  Base + TeamScopedMixin + models_registry
│   ├── pagination/            │  ⭐ 커서 페이지네이션 (별도 CLAUDE.md)
│   ├── repository/            │  ⭐ TeamScopedRepoMixin (별도 CLAUDE.md)
│   ├── schemas/               │  RequestSchema / ResponseSchema / Nested
│   ├── service/               │  (현재 미사용, 향후 cross-domain service)
│   └── utils/                 │  contextvars 등
│
├── cache/                     ─ Redis 클라이언트 (read/write split)
├── database/                  ─ SQLAlchemy 엔진 / 세션 / 의존성
│
├── auth/                      ─ 인증 / OAuth / OTP / 토큰 가드
│   ├── const/                 │  토큰 enum, 메시지 코드
│   ├── oauth/                 │  Google / Kakao / Apple provider
│   ├── tokens/                │  access_token / refresh_token / basic_token 가드
│   ├── utils/                 │  토큰 생성, 검증 헬퍼
│   └── repository.py / service.py / router.py / schemas/
│
├── rbac/                      ─ 권한 모델 + permission_guard + 캐시 (role 가드 추가됨)
├── user/                      ─ 글로벌 유저 + current_user dependency + RolesEnum
├── team/                      ─ ⭐ 표준 도메인 레퍼런스 + get_team_scope dependency
├── invite/                    ─ 팀 초대 (코드 기반)
├── api_key/                   ─ 팀당 API 키 (외부 개발자 통합)
├── file/                      ─ 폴리모픽 파일 (presigned URL)
│
│  ─── TMS Master Data (Phase B) ───────────────────────
├── customer/                  ─ 화주 / 거래처
├── terminal/                  ─ 항만 터미널
├── vessel/                    ─ 선박
├── location/                  ─ 위치 (창고 / 픽업 / 하역지)
├── driver/                    ─ 운전기사 (모바일 앱 사용자의 기사 마스터)
├── truck/                     ─ 트럭
├── equipment_pool/            ─ 장비 풀
├── chassis/                   ─ 샤시
│
│  ─── D/O / Container / Leg (Phase C) ────
├── delivery_order/            ─ ⭐ TMS 대표 도메인 (헤더, state machine, Hold/Cancel overlay) + D/O add-on
├── container/                 ─ D/O 의 컨테이너 라인 (=Shipment) + container_event
├── container_stop/            ─ 컨테이너의 정차 지점 (Point: 타입 Terminal/Yard/Customer)
├── chassis_event/             ─ 샤시 이벤트 (append-only)
├── leg/                       ─ 트럭 한 대의 운송 구간 (state machine, apply_load_type/reissue)
├── leg_layer/                 ─ leg Add-on (추가요금 한 줄, 중복 가능 — addon 마스터 인스턴스)
├── leg_driver_segment/        ─ leg 안에서 driver 가 바뀌는 구간
├── load_type_template/        ─ Leg 청사진 템플릿 → leg 자동생성
├── street_turn/               ─ 컨테이너 직접 이전 (창고 우회) — 승인 워크플로우
├── dual_transaction/          ─ 반납 leg + 픽업 leg 1드라이버 묶음
│
│  ─── 요율 서브시스템 (원자+존 레이어) ────────────────────
├── rate_zone/                 ─ 원자(zip/city) 묶음 레이어 존 — 글로벌/그룹 스코프 + geojson
├── rate_group/                ─ 정산/요율 그룹 (method ZIP/CITY/MILE/HOURLY, 디폴트+상속) + 플랫행 entries API
├── rate_sheet/                ─ 요율표 슬롯 + rate_entry(양방향 ↔, 유효일자) + lane/versioning/resolve(사다리)
├── driver_rate_assignment/    ─ 드라이버↔요율그룹 배정 (유효일자, 미배정=ZIP 디폴트 폴백)
├── addon/                     ─ 부가요금 타입 마스터 (옛 accessorial; leg/D-O add-on 인스턴스가 참조)
├── rate_import/               ─ Excel/CSV 입출력
│
│  ─── 정산 · 청구 (재설계) ──────────────────────────────
├── payroll/                   ─ 드라이버 정산 (settlement/line/charge) — RateResolver snapshot
├── invoice/                   ─ 고객 청구 (cost-plus 원가프리필+마진)
├── audit_log/                 ─ 활동 타임라인 (append-only)
│
│  ─── Mobile / Realtime / AI (Phase D) ──────────────────
├── location_ping/             ─ driver 의 실시간 위치 (append-only)
├── push_token/                ─ FCM / APNS 토큰 등록
├── notification/              ─ 알림 (in-app + push)
├── realtime/                  ─ WebSocket gateway + entity event 발행
├── ai_intake/                 ─ AI 자동 입력 (사진 → D/O 추출)
├── analytics/                 ─ 분석 / 집계 endpoint
└── driver_mobile/             ─ ⭐ BFF — driver 앱 전용 라우팅 (model/repo 없음)
```

---

## 2. 도메인 분류

| 카테고리 | 도메인 폴더 | TeamScoped? | 모델 있음? | 비고 |
| --- | --- | --- | --- | --- |
| 시스템 | `common`, `cache`, `database` | — | — | 인프라 |
| 글로벌 마스터 | `user`, `team`, `rbac/permissions`, `file` | ❌ | ✅ | 멀티테넌시 예외 |
| 인증 | `auth`, `invite`, `api_key` | 부분 | ✅ | invite/api_key 는 팀 scoped |
| 비즈니스 마스터 | `customer`, `terminal`, `vessel`, `location`, `driver`, `truck`, `equipment_pool`, `chassis` | ✅ | ✅ | TMS 마스터 |
| 비즈니스 트랜잭션 | `delivery_order`, `container`, `container_stop`, `chassis_event`, `leg`, `leg_layer`, `leg_driver_segment`, `load_type_template`, `street_turn`, `dual_transaction` | ✅ | ✅ | D/O ↔ Leg 핵심 워크플로우 |
| Rate (원자+존 레이어) | `rate_zone`, `rate_group`, `rate_sheet`, `driver_rate_assignment`, `addon`, `rate_import` | ✅ | ✅ | 요율 서브시스템 (양방향 ↔ 셀/해석 사다리/유효일자/4방식 ZIP·CITY·MILE·HOURLY) |
| 정산 · 청구 (재설계) | `payroll`, `invoice`, `audit_log` | ✅ | ✅ | 드라이버 정산 + 고객 청구(cost-plus) |
| Mobile / Realtime | `location_ping`, `push_token`, `notification`, `realtime` | ✅ | ✅ | 모바일 백엔드 |
| AI / Analytics | `ai_intake`, `analytics` | ✅ | ai_intake ✅ / analytics ❌ | AI 자동입력 / 집계 |
| BFF | `driver_mobile` | — | ❌ | 다른 도메인 service 조립 |

---

## 3. 의존 방향 (단방향) — 절대 깨지 마라

```
                ┌────────────┐
                │  common/   │   ← 모든 도메인이 의존, 자신은 도메인 의존 ❌
                └─────┬──────┘
                      │
   ┌──────────────────┼──────────────────────┐
   ↓                  ↓                      ↓
┌──────────┐    ┌──────────────┐      ┌───────────────┐
│  auth/   │ ←  │  team/ rbac/ │ ←    │ 도메인 layer   │
│  user/   │    │  invite/     │      │ (D/O, Leg ...) │
│  file/   │    │  api_key/    │      └───────────────┘
└──────────┘    └──────────────┘            ↑
                                              │
                                ┌────────────────────────┐
                                │ driver_mobile/ (BFF)   │
                                │ — 위의 도메인을 조립    │
                                └────────────────────────┘
```

### 폴더별 의존 가능 / 금지

| 폴더 | 의존 가능 | 금지 |
| --- | --- | --- |
| `common/` 모든 하위 | dart 표준, 외부 라이브러리, `common/` 다른 하위 | 도메인 코드 (`auth/`, `team/`, ...) |
| `auth/` | `common/`, `user/`, `team/`, `rbac/`, `api_key/`, `cache/`, `database/` | 비즈니스 도메인 (D/O, leg, etc.) |
| `user/`, `team/`, `rbac/` | `common/`, 서로, `auth/` 의 일부 dependency | 비즈니스 도메인 |
| `customer/`, `terminal/`, ... (마스터) | `common/`, `auth/`, `team/`, `rbac/`, `user/`, **다른 마스터 도메인 model** | 트랜잭션 도메인 (`delivery_order`, `leg`, ...) |
| `delivery_order/`, `leg/`, ... (트랜잭션) | `common/`, `auth/`, `team/`, `rbac/`, `user/`, **마스터 도메인** | `driver_mobile/` |
| `realtime/`, `notification/`, `push_token/` | `common/`, `team/`, **모든 트랜잭션 도메인 model** (publish 시) | `driver_mobile/` |
| `driver_mobile/` | **모든 도메인의 service / schema** (조립) | 자체 model/repo 만들기 |

**원칙**:
- 도메인은 자신보다 **위 layer** 만 의존. 하위 layer 의 service 를 직접 호출 금지 (반대 방향).
- 같은 layer 의 도메인끼리는 **모델 import 가능** (예: `delivery_order` 의 service 가 `container.model.ContainerModel` 사용). 단 service → service 직접 호출은 금지 (Repository 직접 주입).
- `driver_mobile` 은 BFF 라 모든 도메인을 조립할 수 있지만, **자체 model 만들지 마라**.

---

## 4. "어디에 둘지" 결정 트리

```
새 코드를 만들어야 한다 — 어디로?
│
├── DB 테이블이 추가됨 ──────────────────→ 새 도메인 폴더 또는 기존 도메인 model.py
│   │
│   ├── 새 비즈니스 개념 → 새 도메인 (src/<domain>/) 생성
│   ├── 기존 도메인의 추가 필드 → 기존 model.py 수정 + alembic
│   └── 기존 도메인의 라인 (1:N) → 같은 도메인 폴더 안 별도 파일 또는
│                                  같은 도메인의 새 model (예: delivery_order/state_machine.py 처럼)
│
├── HTTP 엔드포인트 추가 ───────────────→ 도메인 결정 후 router.py
│   │
│   ├── 일반 API → <domain>/router.py
│   ├── 모바일 app 전용 → src/driver_mobile/router.py
│   └── 외부 개발자용 (API Key) → 같은 router 안에 별도 가드
│
├── 비즈니스 로직 ────────────────────→ <domain>/service.py
│   │
│   ├── 단일 도메인 로직 → service.py 의 메서드
│   ├── 상태 전이 → <domain>/state_machine.py (별도 파일)
│   └── 두 도메인 이상 조립 → 어느 도메인이 주체인지 결정 후
│                              그 도메인의 service.py 안에서 다른 Repository 직접 주입
│
├── 모바일 앱 응답 형태 ─────────────────→ driver_mobile/schemas/response.py + driver_mobile/service.py
│                                          (다른 도메인 service 호출 → 모바일 친화 응답으로 변환)
│
├── 권한 코드 추가 ──────────────────────→ rbac/const/const.py + DEFAULT_*_CODES 매핑
│
├── 새 role ──────────────────────────→ user/const/roles.py (RolesEnum)
│
├── 푸시/알림 발송 ──────────────────────→ notification/service.py 호출 (도메인 service 안에서)
│
├── WebSocket 이벤트 ──────────────────→ <domain>/service.py 의 mutation 끝에
│                                        publish_entity_event(redis, team_id, "<domain>.<action>", entity)
│
├── 파일 업로드 ────────────────────────→ file/ + file/const/domains.py 에 새 도메인 등록
│
├── Celery 백그라운드 작업 ──────────────→ <domain>/tasks/<task_name>.py + celery_app.py imports
│
├── 외부 API 호출 ──────────────────────→ <domain>/ai/ 또는 <domain>/providers/ 하위 폴더 (vessel/ais/ 패턴 참고)
│
└── 공통 유틸 (도메인 무관) ─────────────→ common/utils/<area>/<file>.py
```

---

## 5. types 분류 (이 프로젝트의 Pydantic / SQLAlchemy 분류)

| 종류 | 위치 | 베이스 |
| --- | --- | --- |
| Entity (DB 모델) | `<domain>/model.py` | `Base, TeamScopedMixin` 이중 상속 |
| Mini Entity (목록 표시용 경량) | 같은 model.py 또는 `<domain>/mini.py` | 보통 Pydantic 으로 직접 (DB X) |
| Request Schema | `<domain>/schemas/request.py` | `RequestSchema` |
| Response Schema | `<domain>/schemas/response.py` | `ResponseSchema` |
| Detail Response | `<domain>/schemas/response.py` | `ResponseSchema` (eager load 관계 포함) |
| Paginate Request | `<domain>/schemas/request.py` | `BasePaginationSchema` |
| Bulk Request / Response | `<domain>/schemas/{request,response}.py` | Request/Response Schema |
| State Machine Context | `<domain>/state_machine.py` | `@dataclass` (Pydantic 아님 — 내부 전용) |
| BFF Response | `driver_mobile/schemas/response.py` | `ResponseSchema` — 다른 도메인 schema 를 nested 로 포함 가능 |

---

## 6. import 규칙

### 6.1 절대 경로

```python
# 좋음
from common.exceptions.base import AppException
from team.dependencies.get_team_scope import get_team_scope
from delivery_order.model import DeliveryOrderModel

# 나쁨
from ..common.exceptions import AppException
from ..model import DeliveryOrderModel
```

같은 파일 폴더 안만 상대 import 가능 (드물게):
```python
from .const.status import DeliveryStatus   # 같은 도메인 안
```

### 6.2 `from __future__ import annotations`

모든 model.py / schema 파일 첫 줄에 추가 — 자기 참조 / forward reference 안전:

```python
from __future__ import annotations
```

### 6.3 import 순서

```python
# 1. 표준 라이브러리
from __future__ import annotations
from datetime import datetime
from typing import Optional, List

# 2. 외부 라이브러리
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# 3. 프로젝트 내부 — common 부터
from common.exceptions.base import AppException
from common.pagination.schemas.pagination_response import CursorPaginationResult

# 4. 도메인 (auth, team, rbac 등 → 비즈니스 도메인)
from auth.tokens.access_token import access_token
from team.dependencies.get_team_scope import get_team_scope

# 5. 현재 도메인
from delivery_order.service import DeliveryOrderService
from delivery_order.schemas.request import DeliveryOrderCreateRequest
```

---

## 7. 새 도메인 만들 때 (체크리스트 요약)

자세한 단계는 루트 `CLAUDE.md` 의 "Adding a New Domain Module" 참조.

핵심 순서:
1. `src/<domain>/` 폴더 생성 — `team/` 구조 복제
2. `model.py` — `(Base, TeamScopedMixin)` 이중 상속
3. `repository.py` — `TeamScopedRepoMixin` 상속
4. `service.py` — `__init__(db, team_id)`
5. `router.py` — `_1: None = Depends(access_token)` + `_2: None = Depends(permission_guard(...))` + `team_id: int = Depends(get_team_scope)`
6. `schemas/{request,response}.py`
7. `common/model/models_registry.py` 에 import 추가
8. `main.py` 에 `include_router`
9. `alembic revision --autogenerate -m "add <domain>"` → `alembic upgrade head`
10. `rbac/const/const.py` 에 권한 코드 추가
11. WebSocket event 필요하면 service mutation 끝에 `publish_entity_event(...)`
12. 모바일 노출이 필요하면 `driver_mobile/router.py` 에 BFF 엔드포인트

---

## 8. 관련 문서

- [`../CLAUDE.md`](../CLAUDE.md) — 루트 헌법
- [`common/CLAUDE.md`](./common/CLAUDE.md) — 공통 인프라
- [`common/pagination/CLAUDE.md`](./common/pagination/CLAUDE.md) — 페이징 / DELETE / WS / sync
- [`common/repository/CLAUDE.md`](./common/repository/CLAUDE.md) — TeamScopedRepoMixin
- [`auth/CLAUDE.md`](./auth/CLAUDE.md) — 가드 / JWT / OTP
- [`team/CLAUDE.md`](./team/CLAUDE.md) — ⭐ 표준 도메인 레퍼런스
- [`rbac/CLAUDE.md`](./rbac/CLAUDE.md) — 권한 + role 가드
- [`delivery_order/CLAUDE.md`](./delivery_order/CLAUDE.md) — ⭐ TMS 대표 도메인 + state machine
- [`driver_mobile/CLAUDE.md`](./driver_mobile/CLAUDE.md) — ⭐ BFF + 모바일 라우팅
