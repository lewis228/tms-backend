# src/common/CLAUDE.md

공통 인프라. **도메인 코드는 여기 있는 유틸을 재구현하지 말고 import해서 써야 한다.**

---

## ⭐ 핵심 원칙 — Team 이 멀티테넌시 루트

이 레포의 모든 도메인 데이터는 팀을 기점으로 존재한다. 세부 규약은 `src/team/CLAUDE.md` (표준 도메인 레퍼런스) 와 `src/common/repository/CLAUDE.md` (`TeamScopedRepoMixin`) 참조. 여기선 common 폴더가 제공하는 인프라만 다룬다.

---

## 폴더 구조

```
common/
├── const/          # Pydantic Settings, filter_mapper 등 전역 상수
├── email/          # SMTP 발송 유틸
├── exceptions/     # AppException 계층 + 전역 핸들러
├── lifecycle/      # FastAPI lifespan (startup/shutdown)
├── logging/        # structlog 설정 + 프로세서
├── middleware/     # CORS, Auth, LogContext, AccessLog
├── model/          # SQLAlchemy Base + TeamScopedMixin + models_registry
├── pagination/     # ⭐ 커서 페이징 — 별도 CLAUDE.md (common/pagination/CLAUDE.md)
├── repository/     # ⭐ TeamScopedRepoMixin — 별도 CLAUDE.md (common/repository/CLAUDE.md)
├── schemas/        # RequestSchema / ResponseSchema / SuccessResponseSchema / Nested
└── utils/          # contextvars 등
```

---

## 1. Exceptions (`common/exceptions/`)

### 계층

모든 도메인 예외는 `AppException`을 상속하거나 인라인 생성한다. `AppException`은 `HTTPException`의 확장이며, 전역 핸들러가 다음 JSON을 반환한다:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "리소스을(를) 찾을 수 없습니다.",
    "status_code": 404,
    "detail": { ... }
  }
}
```

### 기본 제공 서브클래스

| 클래스 | HTTP | code |
| --- | --- | --- |
| `NotFoundException(target: str)` | 404 | `NOT_FOUND` |
| `UnauthorizedException(message)` | 401 | `UNAUTHORIZED` |
| `ForbiddenException(message)` | 403 | `FORBIDDEN` |
| `ConflictException(message)` | 409 | `CONFLICT` |
| `BadRequestException(message, code="BAD_REQUEST")` | 400 | 기본 `BAD_REQUEST`, 커스텀 가능 |

### 도메인 예외 정의 규약

**원칙**: 새 서브클래스를 파일로 빼지 않고, **서비스에서 인라인으로 `AppException(code=..., message=..., status_code=...)` 호출**. 실제 코드가 이 관행을 따른다 (`auth/service.py`의 `USE_OAUTH_LOGIN`, `OTP_EXPIRED` 등).

```python
# service.py
raise AppException(
    code="MBL_ALREADY_TRACKING",
    message="이미 추적 중인 MBL입니다.",
    status_code=status.HTTP_409_CONFLICT,
)
```

기본 서브클래스로 충분하면 그냥 쓴다:

```python
raise NotFoundException("Shipment")   # → "Shipment을(를) 찾을 수 없습니다."
raise ConflictException("이미 팀 멤버입니다.")
```

### 전역 핸들러 (`main.py`에 등록됨)

- `AppException` → 사용자 정의 코드/메시지
- `RequestValidationError` → 422, `VALIDATION_ERROR`
- `StarletteHTTPException` → `HTTP_{status}`
- `asyncio.TimeoutError` → 504, `TIMEOUT`
- `SQLAlchemyError` → MySQL 에러코드 매핑 (3024=504, 1205/1213=409, 나머지=500)
- 모든 기타 `Exception` → 500, full traceback 로그

**라우터/서비스에서 `try/except`로 예외를 먹지 마라.** 전역 핸들러가 일관된 포맷을 만든다. 외부 시스템(Celery/Redis/OAuth redirect) 상호작용에서만 국소 try/except 허용.

---

## 2. Schemas (`common/schemas/`)

### Base 클래스

모든 도메인 스키마는 다음 두 베이스 중 하나를 상속해야 한다:

**`RequestSchema`** — 클라이언트 → 서버
- `str_strip_whitespace=True` — 문자열 앞뒤 공백 자동 제거
- `extra="forbid"` — 알 수 없는 필드 오면 422
- `alias_generator=to_camel` + `populate_by_name=True` — 클라이언트가 camelCase로 보내도 snake_case로 매핑

**`ResponseSchema`** — 서버 → 클라이언트
- `from_attributes=True` — ORM 객체에 `model_validate(orm)` 바로 가능
- `extra="ignore"` — 여분 필드 무시
- **datetime 자동 UTC+Z 직렬화** — 내부 ISO-8601 문자열이 `...+00:00`이든 naive든 전부 `...Z`로 치환

### SuccessResponseSchema

단순 ok 응답용. 쓸 일이 있을 때만.

```python
class SuccessResponseSchema(ResponseSchema):
    success: bool = True
    message: Optional[str] = None
    status_code: int = 200

    @classmethod
    def ok(cls): ...
    @classmethod
    def created(cls): ...
    @classmethod
    def accepted(cls): ...
```

### Nested 스키마

관계 객체 축약용. `common/schemas/nested.py`:
- `FileNestedSchema` — 파일 최소 정보
- `UserNestedSchema` — 사용자 최소 정보
- `PermissionGroupNestedSchema` — 권한 그룹 최소 정보

도메인 스키마에서 재사용:

```python
class UserListItemResponseSchema(ResponseSchema):
    id: int
    email: str
    teams: List[UserTeamRowResponseSchema] = []
    files: List[FileNestedSchema] = []
```

### 페이지네이션 응답 타입

모든 페이징 엔드포인트는 `CursorPaginationResult[T]`를 `response_model`로 쓴다. 상세는 `common/pagination/CLAUDE.md`.

---

## 3. Middleware (`common/middleware/`)

`main.py`에서 **역순**으로 등록되므로 실행 순서는 (외→내):

1. **CORSMiddleware** — CORS 헤더 / 프리플라이트
2. **LogContextMiddleware** (`context.py`)
   - `X-Request-ID` 헤더 읽거나 새로 생성
   - `request_id_ctx_var` contextvar에 저장 (structlog가 자동 주입)
   - 응답에도 `X-Request-ID` 헤더 붙임
3. **AuthMiddleware** (`auth.py`)
   - `Authorization: Bearer` 토큰 디코드 시도 (실패해도 raise 안 함)
   - 성공 시 `request.state.user` 세팅 + structlog에 `user_id` 바인드
   - **엄격한 JWT 검증은 `bearer_token` dependency가 수행** — 미들웨어는 무른 확인만
4. **AccessLogMiddleware** (`access_log.py`)
   - method/path/status/duration_ms 로깅
   - `/health`, `/metrics`, `/public/*` 스킵

**DelayMiddleware**는 로컬 네트워크 지연 시뮬레이션용으로 정의돼 있으나 기본 비활성.

---

## 4. Logging (`common/logging/`)

### 사용법

```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("shipment_created", shipment_id=123, mbl="ABC123", team_id=1)
logger.warning("scrape_retry", attempt=3, mbl="ABC123")
logger.error("celery_dispatch_failed", error=str(e))
logger.exception("unexpected_error")   # try/except 안에서만 — traceback 포함
```

### 자동 주입되는 필드

매 요청마다 자동으로 모든 로그에 포함:
- `request_id` — 미들웨어가 주입 (로그 간 상관관계 추적)
- `user_id` — JWT 디코드 성공 시 미들웨어가 바인드
- `timestamp` — ISO 8601 + Z
- `level` — INFO/WARNING/ERROR/DEBUG

도메인 코드는 `request_id`, `user_id`를 **수동으로 전달할 필요 없다**.

### 환경별 렌더링

- ENV=dev → `ConsoleRenderer(colors=True)` + DEBUG
- ENV=prod → `JSONRenderer()` + WARNING (LOG_LEVEL 환경변수로 오버라이드 가능)

### 민감정보 마스킹

`redact_sensitive` 프로세서가 email/phone/token을 자동 마스킹한다.

---

## 5. Settings (`common/const/settings.py`)

### 로딩 순서

1. `config_bootstrap.load_env()`가 import 시 1회 실행
2. `.env` 파일 로드 (로컬) 또는 AWS Parameter Store 조회 (EC2)
3. alias 적용 (예: `DB_USER` → `DB_USERNAME`, scraping 레포 호환)
4. EC2에서 `MINIO_ACCESS_KEY`가 비어있으면 IAM Role 사용 경로 활성화
5. `Settings(BaseSettings)` 인스턴스 생성 (`os.environ`에서 읽음)

### 주요 그룹

- 서버/프로토콜: `PROTOCOL`, `HOST`, `PORT`, `ROOT_PATH` (페이징 `next` URL에 사용)
- DB: `DB_HOST`/`DB_WRITE_HOST`/`DB_READ_HOST`, `DB_READ_TIMEOUT=30`, `DB_WRITE_TIMEOUT=600`, `DB_MAX_EXEC_MS=30000`
- Redis: `REDIS_HOST`/`REDIS_WRITE_HOST`/`REDIS_READ_HOST`, `REDIS_SSL` (ElastiCache TLS)
- Auth: `JWT_SECRET`, `ACCESS_TTL=1800`, `REFRESH_TTL=8000`, `OAUTH_STATE_TTL=600`, `OTP_TTL=180`, `OTP_OK_TTL=900`, `OTP_MAX_TRIES=5`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_SENDER` — 비어있으면 콘솔 출력(개발)
- MinIO/S3: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`
- OAuth: Google/Kakao/Apple (옵션)
- ORM: `ORM_LAZY_DEFAULT = "raise"` (lazy load 금지)

### 헬퍼 프로퍼티

```python
settings.is_production           # ENV == "production"
settings.is_db_read_write_split  # DB_WRITE_HOST and DB_READ_HOST 둘 다 있을 때
settings.is_redis_read_write_split
settings.cookie_secure           # prod면 True
```

### 새 설정 추가

```python
# common/const/settings.py
class Settings(BaseSettings):
    MY_FEATURE_ENABLED: bool = False   # Optional이면 default 명시
    MY_REQUIRED_VALUE: str              # 타입만 적으면 필수 — .env에 없으면 부팅 실패
```

도메인 코드:
```python
from common.const.settings import settings
if settings.MY_FEATURE_ENABLED:
    ...
```

`.env` (로컬) 또는 AWS Parameter Store (EC2)에 값 등록.

---

## 6. Email (`common/email/smtp_sender.py`)

```python
from common.email.smtp_sender import send_email_html

await send_email_html(
    to="user@example.com",
    subject="Welcome",
    html="<h1>환영합니다</h1>",
    text_fallback="환영합니다",
)
```

SMTP 환경변수가 전부 세팅돼 있으면 실제 발송, 아니면 콘솔 출력 (로컬 개발).

---

## 7. Base Model (`common/model/base_model.py`)

```python
@as_declarative()
class Base:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="RESTRICT"), nullable=True)
```

### 모든 모델은 반드시

1. `Base` 상속
2. `__tablename__` 명시 (snake_case 복수형 + 복합 도메인 prefix — 예: `ocean_shipments`)
3. `common/model/models_registry.py`에 import 추가

### 감사 필드 (`created_by_user_id` / `updated_by_user_id`)

**현재 자동 채움 없음.** `database/event_hooks.py`는 비어있다. 서비스 레이어에서 수동 설정:

```python
shipment = ShipmentModel(
    ...,
    created_by_user_id=me.id,
)
# update 시:
shipment.updated_by_user_id = me.id
```

`updated_at`만 `onupdate=func.now()`로 자동 갱신된다.

### Soft Delete

- 마스터 데이터는 `is_active=False`로 논리 삭제
- 하드 삭제는 FK `ondelete="RESTRICT"`로 차단 (orphan 방지)
- **모든 read 쿼리는 `.where(Model.is_active.is_(True))` 명시 적용** — 자동 필터 없음

예외: 이력 보존 목적인 API key는 `is_active` 대신 `revoked_at` 사용 (특수 케이스).

---

## 8. TeamScopedMixin (`common/model/team_scoped_mixin.py`)

⭐ **팀 scoped 모델의 기본 인프라.** 모든 도메인 모델은 `(Base, TeamScopedMixin)` 이중 상속이 기본값. 예외는 전역 모델 (User/Team/UserTeam 조인/Permission 마스터/FileAsset 폴리모픽) 만.

```python
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin

class ShipmentModel(Base, TeamScopedMixin):
    __tablename__ = "ocean_shipments"
    mbl: Mapped[str] = mapped_column(String(50), nullable=False)
    # ...
```

자동 추가:
- `team_id: Mapped[int]` — `FK → teams.id ondelete="CASCADE"`, `index=True`, `nullable=False`
- `team` relationship — `lazy="selectin"` (⚠️ `ORM_LAZY_DEFAULT="raise"` 예외 — N+1 주의)

### `__with_team_rel__ = False` — 라인 테이블 예외

헤더-라인 구조에서 **라인 쪽** 은 `.team` 관계를 헤더 통해 접근하므로 라인에 `.team` 이 또 있으면 충돌/중복 로드 유발. 라인 테이블엔 `__with_team_rel__ = False` 를 명시:

```python
class ContainerModel(Base, TeamScopedMixin):
    __tablename__ = "ocean_containers"
    __with_team_rel__ = False              # ← .team 제거, 헤더 통해 접근
    shipment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # ...
```

### 복합 FK + UniqueConstraint 패턴 (필수)

팀 scoped 모델은 반드시 `UniqueConstraint("team_id", "id")` 갖고, 자식 테이블은 단순 FK 가 아닌 복합 FK 를 쓴다:

```python
__table_args__ = (
    UniqueConstraint("team_id", "id", name="uq_<table>_team_id_id"),
    ForeignKeyConstraint(
        ["team_id", "parent_id"],
        ["parent_table.team_id", "parent_table.id"],
        ondelete="CASCADE",
        name="fk_<table>_<ref>_team_id_id",
    ),
    Index("ix_<table>_team_id_id", "team_id", "id"),     # team_id 항상 leftmost
    # ...
)
```

세부 규약 (인덱스, primaryjoin 등) 은 **`src/team/CLAUDE.md`** 와 **`src/ocean/CLAUDE.md`** 참조.

### 팀 scoped 테이블 목록 수집 헬퍼

```python
from common.model.team_scoped_mixin import get_team_scoped_table_names

names = get_team_scoped_table_names()  # 런타임에 metadata 에서 team_id FK 가진 테이블 수집
# → ["ocean_shipments", "ocean_containers", "api_keys", "tags", ...]
```

시스템 배치 작업이나 diagnostic 용.

`.team` 관계가 필요 없으면 `__with_team_rel__ = False`.

---

## 9. models_registry.py

모든 모델은 여기에 import해야 Alembic autogenerate가 감지한다.

```python
from common.model.base_model import Base

from user.model import UserModel
from team.model import TeamModel, UserTeamModel
from rbac.model import PermissionModel, PermissionGroupModel, PermissionGroupPermission
from file.model import FileAssetModel
from api_key.model import ApiKeyModel

from ocean.shipment.model import ShipmentModel
from ocean.container.model import ContainerModel
from ocean.tracking_event.model import TrackingEventModel
from ocean.scrape_log.model import ScrapeLogModel
```

새 모델 추가 시 반드시 이 파일 수정 → `alembic revision --autogenerate -m "add <model>"`.

---

## 10. Lifecycle (`common/lifecycle/lifespan.py`)

FastAPI `lifespan` context manager가 startup/shutdown 처리:

**Startup**:
1. request_id 세팅
2. DB 연결 검증 + 타임아웃 설정 확인
3. Redis 연결 검증
4. MinIO 버킷 존재 확인
5. `all_services_connected` 로그

**Shutdown**:
1. SQLAlchemy 엔진 dispose
2. Redis 연결 종료
3. `graceful_shutdown_tasks()` (커스텀 cleanup 훅)

도메인 코드는 **DB/Redis/MinIO 재초기화 금지**. 글로벌 세션이나 커넥션 풀 만들지 말고 반드시 dependency 주입 사용.

---

## 11. Database Dependencies (`database/dependencies.py`)

```python
async def get_write_db() -> AsyncGenerator[AsyncSession, None]:
    """쓰기 세션. 성공 시 auto-commit, 예외 시 rollback."""

async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """읽기 세션. commit 안 함."""
```

**규칙**:
- GET 엔드포인트 → `get_read_db`
- POST/PATCH/DELETE → `get_write_db`
- **Service/Repository에서는 `commit()` 호출 금지** — yield 후 auto-commit만 신뢰
- Repository write 메서드는 `await db.flush()` + 필요 시 `await db.refresh(obj)`

### Timed Session

`TimedAsyncSession`이 모든 `execute()`를 `asyncio.wait_for`로 래핑:
- SELECT → 30초 (`DB_READ_TIMEOUT`)
- INSERT/UPDATE/DELETE → 600초 (`DB_WRITE_TIMEOUT`)

초과 시 `asyncio.TimeoutError` → 전역 핸들러가 504로 변환.

---

## 12. Cache Dependencies (`cache/`)

```python
async def get_write_redis() -> Redis:   # SET / DEL / INCR
async def get_read_redis() -> Redis:    # GET / EXISTS / TTL
async def get_redis_client() -> RedisClient:   # 읽기/쓰기 분리 래퍼
async def get_redis() -> Redis:         # write_redis 별칭
```

- 커넥션 풀: read=50, write=10 (read-heavy 가정)
- AWS ElastiCache TLS는 `REDIS_SSL=True`로 활성화
- `decode_responses=True` — bytes 아니라 str 반환

`RedisClient` 래퍼는 명시적 read/write 분리가 필요할 때:

```python
client: RedisClient = await get_redis_client()
await client.set("k", "v")   # → write_redis
val = await client.get("k")  # → read_redis
await client.get_from_primary("k")  # 읽기 replica lag 우회
```

---

## 13. Utils (`common/utils/`)

- `contextvars.py` — `request_id_ctx_var`, `user_id_ctx_var` (structlog 자동 주입용)

**규약**: 유틸은 순수 함수로. stdlib (`datetime`, `json`, `secrets`)이나 검증된 라이브러리(`cryptography`)로 해결 가능한 건 재구현 금지.

---

## 14. Filter Mapper (`common/const/filter_mapper.py`)

페이지네이션 request 스키마의 `where__<field>__<op>` 파라미터가 어떤 SQL로 변환되는지 정의. **커스텀 필터 연산자 추가 시에만 이 파일 수정**.

제공되는 연산자: `equal`, `i_like`, `like`, `more_than`, `less_than`, `more_than_or_equal`, `less_than_or_equal`, `in`, `between`, `starts_with`, `ends_with`, `is_null`. 세부는 `common/pagination/CLAUDE.md`.

---

## 알려진 상태 (정보 공유)

- `database/event_hooks.py`가 비어있어 감사 필드는 수동 채움 (상기 Base Model 섹션)
- `common/logging/config.py`의 `setup_logging()`은 정의만 있고 lifespan에서 호출 안 됨 — prod에서 구조화 로깅이 의도대로 동작 안 할 수 있음 (별도 이슈로 추적)
- `permission_guard`, `team_admin_guard`, `access_token` dependency는 정의만 있고 현재 라우터에서 미사용 (RBAC 확장 시 활성화 예정)
