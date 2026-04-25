# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ⭐ 가장 중요한 원칙 — Team이 멀티테넌시 루트

> **모든 도메인 데이터는 팀(Team)을 기점으로 존재한다.** `User`, `Team`, `UserTeam` 조인, `Permission` 마스터, `FileAsset` 폴리모픽 이 네 가지만 예외고 나머지는 전부 `team_id`를 갖는다. 팀이 삭제되면 그 팀 소유의 shipment/container/event/scrape_log/tag/api_key 등 전부 CASCADE로 물리 삭제된다.
>
> 크로스 테넌시 누출은 **3단 방어선**으로 차단:
> 1. **DB**: `TeamScopedMixin`이 주입한 `team_id FK → teams.id ondelete=CASCADE` + 복합 FK `(team_id, xxx_id)` + `UniqueConstraint(team_id, id)`
> 2. **ORM**: 모든 relationship의 `primaryjoin`에 `foreign(X.team_id) == Y.team_id` 포함
> 3. **App**: Repository `TeamScopedRepoMixin._require_team()` + Router `Depends(get_team_scope)`
>
> **새 모델/레포/라우터를 만들 때 이 3단 방어선을 모두 세워라.** 세부 규약은 `src/team/CLAUDE.md` (표준 도메인 레퍼런스) 와 `src/ocean/CLAUDE.md` (복합 도메인 템플릿) 참조.

---

## Sub-CLAUDE.md 네비게이션

| 경로 | 역할 |
| --- | --- |
| `src/common/CLAUDE.md` | 예외, 로깅, 미들웨어, Settings, Base model, 공통 스키마 |
| `src/common/pagination/CLAUDE.md` | ⭐ MANDATORY — 커서 페이징 규약 |
| `src/common/repository/CLAUDE.md` | ⭐ `TeamScopedRepoMixin` — Repository 작성 규약 |
| `src/auth/CLAUDE.md` | JWT + API Key 통합 인증, `get_team_scope`, OAuth, OTP |
| `src/rbac/CLAUDE.md` | 권한 모델, 권한 코드, `permission_guard`, 캐시 |
| `src/team/CLAUDE.md` | ⭐ **표준 도메인 레퍼런스** — 새 도메인 만들 때 이 구조 복제 |
| `src/ocean/CLAUDE.md` | ⭐ **복합 도메인 템플릿** — 헤더/라인 + 복합 FK + Celery tasks |

---

## Project Overview

TMS(Transportation Management System) API Server — FastAPI 보일러플레이트 기반.
웹앱(실무자용)과 API(외부 개발자용)를 동시에 제공한다. STE `backend_tracking-api` 를 베이스로 분기한 TMS 전용 백엔드.

## Development Commands

```bash
docker-compose up -d mysql redis minio minio-init        # 인프라만
docker-compose up -d                                      # 전체
PYTHONPATH=src uvicorn main:app --host 0.0.0.0 --port 8080 --app-dir src  # 로컬 앱

alembic upgrade head                                      # 마이그레이션 적용
alembic revision --autogenerate -m "description"          # 새 마이그레이션 생성

cd src && PYTHONPATH=. celery -A celery_app worker --loglevel=info   # Worker
cd src && PYTHONPATH=. celery -A celery_app beat --loglevel=info     # Beat
```

---

## Architecture — 고수준 개요

### Module Pattern (DDD)

모든 도메인은 `src/<domain>/` 아래에:
- `model.py` — SQLAlchemy (`Base, TeamScopedMixin` 이중 상속이 기본)
- `repository.py` — `TeamScopedRepoMixin` 상속
- `service.py` — `__init__(db, team_id)` 시그니처
- `router.py` — `Depends(get_team_scope)` 주입
- `schemas/` — Pydantic (`RequestSchema`/`ResponseSchema` 상속)
- `const/`, `dependencies/` — 필요 시

세부: `src/team/CLAUDE.md`. 복합 도메인은 `src/ocean/CLAUDE.md`.

### 팀 스코프 요청 흐름

```
1. HTTP Request (X-API-Key 또는 Authorization: Bearer)
2. jwt_or_api_key  → AuthResult(auth_type, user_id, team_id, plan)
                     ├─ API Key 경로: 키 row 에서 team_id 추출
                     └─ JWT 경로: X-Team-Id 헤더 검증 (user_teams 멤버십)
3. rate_limit      → API Key 호출자만 (JWT 는 skip)
4. get_team_scope  → auth.team_id None 이면 400
5. ServiceClass(db, team_id)  → Repository 생성자까지 team_id 전파
6. Repository._require_team() → 모든 쿼리 WHERE 첫 조건
```

### Middleware Stack (순서)

`main.py`에서 역순 등록:
1. CORSMiddleware (최외곽)
2. LogContextMiddleware (request_id 주입)
3. AuthMiddleware (JWT 디코드, 실패해도 raise 안 함)
4. AccessLogMiddleware (method/path/status/ms)

### Database

- Async MySQL (SQLAlchemy 2.0 + aiomysql)
- Read/write split: `get_read_db()` / `get_write_db()`
- Base model: `id`, `is_active`, `created_at`, `updated_at`, `created_by_user_id`, `updated_by_user_id`
- Soft delete 원칙, 하드 삭제는 FK `RESTRICT`로 차단
- Query timeout: read 30초, write 600초 (`database/timed_session.py`)

### Infrastructure

- Redis: 세션/캐시/OTP/rate_limit (`cache/`, read/write split)
- MinIO/S3: 파일 (`file/`)
- Logging: structlog + request_id (`common/logging/`)
- Pagination: **커서 기반만** (`common/pagination/`)

---

## Adding a New Domain Module

1. `src/<domain>/` 생성 — `src/team/CLAUDE.md` 구조 복제
2. `model.py` 작성 — **반드시** `(Base, TeamScopedMixin)` 이중 상속 (시스템/글로벌 모델 제외)
3. `repository.py` 작성 — **반드시** `TeamScopedRepoMixin` 상속
4. `service.py` 작성 — `__init__(self, db, team_id)` 시그니처
5. `router.py` 작성 — `Depends(get_team_scope)` 주입
6. `schemas/request.py`, `schemas/response.py` 작성
7. 모델을 `src/common/model/models_registry.py`에 import 등록
8. 라우터를 `src/main.py`에 `include_router`
9. `alembic revision --autogenerate -m "add <domain>"` → migration 확인 → `alembic upgrade head`
10. 파일 업로드 필요하면 `src/file/const/domains.py` 추가
11. RBAC 권한 필요하면 `src/rbac/const/const.py` 추가

복합 도메인(헤더 + 여러 라인 + tasks)이면 `src/ocean/CLAUDE.md` 패턴 따름.

---

## TMS — 비즈니스 컨텍스트

> **STE 분기 메모.** 이 프로젝트는 `ste/backend_tracking-api` 를 베이스로 분기했다. `ocean/`, `vessel/` 등 STE 전용 도메인 코드가 남아 있으므로, TMS 도메인 정의 후 불필요한 모듈은 제거하거나 교체한다.

### 서버 구성

| 레포 | 역할 | 위치 |
| --- | --- | --- |
| **backend_tms-api** | FastAPI + Celery Beat | ~/Develop/tms/backend_tms-api |

Redis(broker) + MySQL(DB) 공유.

### 기술 스택

| 구분 | 기술 |
| --- | --- |
| Task Queue | Celery + Redis |
| 스케줄러 | Celery Beat |
| AI | Claude API (필요 시) |

### 도메인 모듈 (현재 — TMS 도메인 확정 후 갱신)

**팀 scoped (TeamScopedMixin 상속)**:
- `api_key` — 팀당 API 키
- _(TMS 핵심 도메인을 여기에 추가)_

**팀 미소속 (TeamScopedMixin 예외)**:
- `user` — 전역 (한 유저가 여러 팀 소속 가능)
- `team` — 자신이 루트
- `file` — 폴리폴릭 (`domain`+`object_id` 로 소유 연결)
- `rbac/permissions` — 전역 권한 코드 카탈로그 (단, `PermissionGroup` 은 팀 scoped)

### DB 스키마 — 팀 스코프 관점

모든 팀 scoped 테이블은 다음 규약 공통:
- `team_id` 컬럼 NOT NULL + `FK → teams.id ondelete=CASCADE`
- `UniqueConstraint("team_id", "id")` (복합 FK 타겟용)
- 모든 인덱스 `team_id` leftmost
- 자식 테이블의 FK 는 `ForeignKeyConstraint(["team_id", "parent_id"], ["parent.team_id", "parent.id"], ondelete="CASCADE")` 복합 FK

_(TMS 도메인 테이블 목록은 도메인 설계 확정 후 여기에 추가)_

### 전역 삭제 정책 (통일)

| 케이스 | 방식 |
| --- | --- |
| 사용자 삭제 요청 | Soft (`is_active=False`) |
| 팀/헤더 삭제 → 하위 | Hard CASCADE (DB 레벨 자동) |
| API Key 회수 | Soft (`is_active=False`) — `updated_at` 이 회수 시점 |

**하드 삭제는 오직 DB CASCADE 가 트리거할 때만.** 애플리케이션 레벨에선 전부 soft. `revoked_at` 같은 별도 컬럼은 쓰지 않고 `is_active` 하나로 통일.
