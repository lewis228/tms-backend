# src/common/CLAUDE.md

공통 인프라. **도메인 코드는 여기 있는 유틸을 재구현하지 말고 import 해서 써야 한다.**

---

## ⭐ 핵심 원칙 — Team 이 멀티테넌시 루트

이 레포의 모든 비즈니스 데이터는 팀을 기점으로 존재한다. 세부 규약은 `src/team/CLAUDE.md` (표준 도메인 레퍼런스) 와 `src/common/repository/CLAUDE.md` (`TeamScopedRepoMixin`) 참조. 여기선 common 폴더가 제공하는 인프라만 다룬다.

---

## 폴더 구조

```
common/
├── const/          # Pydantic Settings, filter_mapper, path 상수
├── email/          # SMTP 발송 유틸
├── exceptions/     # AppException 계층 + 전역 핸들러
├── lifecycle/      # FastAPI lifespan (startup/shutdown)
├── logging/        # structlog 설정 + 프로세서
├── middleware/     # CORS / Auth / LogContext / AccessLog / Session / Delay / Error
├── model/          # SQLAlchemy Base + TeamScopedMixin + models_registry
├── pagination/     # ⭐ 커서 페이징 — 별도 CLAUDE.md (common/pagination/CLAUDE.md)
├── repository/     # ⭐ TeamScopedRepoMixin — 별도 CLAUDE.md (common/repository/CLAUDE.md)
├── schemas/        # RequestSchema / ResponseSchema / Nested / calc_schemas / custom_field
├── service/        # (현재 비어있음 — cross-domain service 추가 시 사용)
└── utils/          # contextvars 등
```

---

## 1. Exceptions (`common/exceptions/`)

### 계층

모든 도메인 예외는 `AppException` 을 상속하거나 인라인 생성한다. `AppException` 은 `HTTPException` 의 확장이며, 전역 핸들러가 다음 JSON 을 반환한다:

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

**원칙**: 새 서브클래스를 파일로 빼지 않고, **서비스에서 인라인으로 `AppException(code=..., message=..., status_code=...)` 호출**.

```python
# service.py
raise AppException(
    code="DO_ALREADY_DISPATCHED",
    message="이미 디스패치된 D/O 입니다.",
    status_code=status.HTTP_409_CONFLICT,
)
```

예외: state machine 같이 도메인 핵심 위반은 `state_machine.py` 안에 전용 서브클래스 OK:

```python
# delivery_order/state_machine.py
class InvalidStateTransitionError(AppException):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            code="ERR_INVALID_STATE_TRANSITION",
            message=message,
            status_code=422,
            detail=details,
        )
```

기본 서브클래스로 충분하면 그냥 쓴다:

```python
raise NotFoundException("DeliveryOrder")   # → "DeliveryOrder을(를) 찾을 수 없습니다."
raise ConflictException("이미 팀 멤버입니다.")
```

### 전역 핸들러 (`main.py` 에 등록됨)

- `AppException` → 사용자 정의 코드/메시지
- `RequestValidationError` → 422, `VALIDATION_ERROR`
- `StarletteHTTPException` → `HTTP_{status}`
- `asyncio.TimeoutError` → 504, `TIMEOUT`
- `SQLAlchemyError` → MySQL 에러코드 매핑 (3024=504, 1205/1213=409, 나머지=500)
- 모든 기타 `Exception` → 500, full traceback 로그

**라우터/서비스에서 `try/except` 로 예외를 먹지 마라.** 전역 핸들러가 일관된 포맷을 만든다. 외부 시스템 (Celery / Redis / OAuth redirect / external API) 상호작용에서만 국소 try/except 허용.

---

## 2. Schemas (`common/schemas/`)

### Base 클래스

모든 도메인 스키마는 다음 두 베이스 중 하나를 상속해야 한다:

**`RequestSchema`** — 클라이언트 → 서버
- `str_strip_whitespace=True` — 문자열 앞뒤 공백 자동 제거
- `extra="forbid"` — 알 수 없는 필드 오면 422
- `alias_generator=to_camel` + `populate_by_name=True` — 클라이언트가 camelCase 로 보내도 snake_case 로 매핑

**`ResponseSchema`** — 서버 → 클라이언트
- `from_attributes=True` — ORM 객체에 `model_validate(orm)` 바로 가능
- `extra="ignore"` — 여분 필드 무시
- **datetime 자동 UTC+Z 직렬화** — 내부 ISO-8601 문자열이 `...+00:00` 이든 naive 든 전부 `...Z` 로 치환

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
class DeliveryOrderDetailResponseSchema(ResponseSchema):
    id: int
    status: DeliveryStatus
    customer: CustomerNestedSchema     # 도메인별 nested 도 같은 패턴으로
    files: List[FileNestedSchema] = []
    containers: List[ContainerResponseSchema] = []
```

### Calc Schemas (`common/schemas/calc_schemas.py`)

수량 / 금액 / 시간 계산 결과의 표준 응답 형태:

```python
class MoneyAmount(ResponseSchema):
    currency: str
    amount: Decimal
    formatted: str    # "$1,234.56"
```

운임 / 정산 도메인이 공통으로 사용. 새 화폐 단위 / 포맷이 필요하면 여기에만 추가.

### Custom Field (`common/schemas/custom_field.py`)

사용자 정의 필드 (커스텀 컬럼) 의 직렬화 형태. 추후 확장용 — 현재 활성 사용 미사용.

### Version (`common/schemas/version.py`)

`__version__` 같은 메타정보 응답용. 헬스체크 / 시스템 endpoint 에서 사용.

### 페이지네이션 응답 타입

모든 페이징 엔드포인트는 `CursorPaginationResult[T]` 를 `response_model` 로 쓴다. 상세는 `common/pagination/CLAUDE.md`.

---

## 3. Middleware (`common/middleware/`)

`main.py` 에서 **역순**으로 등록되므로 실행 순서는 (외→내):

1. **CORSMiddleware** — CORS 헤더 / 프리플라이트
2. **LogContextMiddleware** (`context.py`)
   - `X-Request-ID` 헤더 읽거나 새로 생성
   - `request_id_ctx_var` contextvar 에 저장 (structlog 가 자동 주입)
   - 응답에도 `X-Request-ID` 헤더 붙임
3. **AuthMiddleware** (`auth.py`)
   - `Authorization: Bearer` 토큰 디코드 시도 (실패해도 raise 안 함)
   - 성공 시 `request.state.user` 세팅 + structlog 에 `user_id` 바인드
   - **엄격한 JWT 검증은 `access_token` dependency 가 수행** — 미들웨어는 무른 확인만
4. **AccessLogMiddleware** (`access_log.py`)
   - method / path / status / duration_ms 로깅
   - `/health`, `/metrics`, `/public/*` 스킵

**그 외**:
- `delay.py` (`DelayMiddleware`) — 로컬 네트워크 지연 시뮬레이션. 기본 비활성.
- `error.py` — 부가 에러 매핑.
- `session.py` — 세션 관련 처리 (cookie 기반 web 세션).
- `rate_limit.py` — 현재 활성 사용 안 함 (필요 시 외부 API 라우터에 부착).

### 헤더 표준

| 요청 헤더 | 용도 |
| --- | --- |
| `Authorization: Bearer <jwt>` | JWT 인증 |
| `X-API-Key: <key>` | API Key 인증 (외부 개발자 통합) |
| `X-Team-Id: <int>` | 팀 스코프 선택 (JWT 호출자 — `get_team_scope` 가 검증) |
| `X-Request-ID` | 추적 ID (없으면 미들웨어가 발급) |
| `X-Client-Type` | `web` / `ios` / `android` / 등 |
| `X-Device-Key` | 디바이스 식별 (모바일 토큰 검증) |
| `X-App-Version` | 앱 버전 (강제 업데이트 / 호환성) |

---

## 4. Logging (`common/logging/`)

### 사용법

```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("delivery_order_created", delivery_order_id=123, team_id=1)
logger.warning("leg_transition_failed", leg_id=456, attempt=3)
logger.error("notification_dispatch_failed", error=str(e))
logger.exception("unexpected_error")   # try/except 안에서만 — traceback 포함
```

### 자동 주입되는 필드

매 요청마다 자동으로 모든 로그에 포함:
- `request_id` — 미들웨어가 주입 (로그 간 상관관계 추적)
- `user_id` — JWT 디코드 성공 시 미들웨어가 바인드
- `timestamp` — ISO 8601 + Z
- `level` — INFO / WARNING / ERROR / DEBUG

도메인 코드는 `request_id`, `user_id` 를 **수동으로 전달할 필요 없다**.

### 환경별 렌더링

- ENV=dev → `ConsoleRenderer(colors=True)` + DEBUG
- ENV=prod → `JSONRenderer()` + WARNING (LOG_LEVEL 환경변수로 오버라이드 가능)

### 민감정보 마스킹

`redact_sensitive` 프로세서가 email / phone / token 을 자동 마스킹.

---

## 5. Settings (`common/const/settings.py`)

### 로딩 순서

1. `config_bootstrap.load_env()` 가 import 시 1회 실행
2. `.env` 파일 로드 (로컬) 또는 AWS Parameter Store 조회 (EC2)
3. alias 적용 (예: `DB_USER` → `DB_USERNAME`, 레거시 호환)
4. EC2 에서 `MINIO_ACCESS_KEY` 가 비어있으면 IAM Role 사용 경로 활성화
5. `Settings(BaseSettings)` 인스턴스 생성 (`os.environ` 에서 읽음)

### 주요 그룹

- 서버 / 프로토콜: `PROTOCOL`, `HOST`, `PORT`, `ROOT_PATH` (페이징 `next` URL 에 사용)
- DB: `DB_HOST` / `DB_WRITE_HOST` / `DB_READ_HOST`, `DB_READ_TIMEOUT=30`, `DB_WRITE_TIMEOUT=600`, `DB_MAX_EXEC_MS=30000`
- Redis: `REDIS_HOST` / `REDIS_WRITE_HOST` / `REDIS_READ_HOST`, `REDIS_SSL` (ElastiCache TLS)
- Auth: `JWT_SECRET`, `ACCESS_TTL=1800`, `REFRESH_TTL=8000`, `OAUTH_STATE_TTL=600`, `OTP_TTL=180`, `OTP_OK_TTL=900`, `OTP_MAX_TRIES=5`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_SENDER` — 비어있으면 콘솔 출력 (개발)
- MinIO/S3: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`
- OAuth: Google / Kakao / Apple (옵션)
- Push: FCM / APNS 키 (driver 앱 푸시)
- SMS: SMS gateway (driver 폰번호 OTP 발송) — Twilio / Aligo / NHN 등 환경별
- ORM: `ORM_LAZY_DEFAULT = "raise"` (lazy load 금지)
- CORS: `ALLOWED_ORIGINS`, `ALLOWED_ORIGIN_REGEX`

### 헬퍼 프로퍼티

```python
settings.is_production           # ENV == "production"
settings.is_db_read_write_split  # DB_WRITE_HOST and DB_READ_HOST 둘 다 있을 때
settings.is_redis_read_write_split
settings.cookie_secure           # prod 면 True
```

### 새 설정 추가

```python
# common/const/settings.py
class Settings(BaseSettings):
    MY_FEATURE_ENABLED: bool = False   # Optional 이면 default 명시
    MY_REQUIRED_VALUE: str              # 타입만 적으면 필수 — .env 에 없으면 부팅 실패
```

도메인 코드:
```python
from common.const.settings import settings
if settings.MY_FEATURE_ENABLED:
    ...
```

`.env` (로컬) 또는 AWS Parameter Store (EC2) 에 값 등록.

### Filter Mapper (`common/const/filter_mapper.py`)

페이지네이션 request 스키마의 `where__<field>__<op>` 파라미터가 어떤 SQL 로 변환되는지 정의. **커스텀 필터 연산자 추가 시에만 이 파일 수정**.

제공되는 연산자: `equal`, `i_like`, `like`, `more_than`, `less_than`, `more_than_or_equal`, `less_than_or_equal`, `in`, `between`, `starts_with`, `ends_with`, `is_null`. 세부는 `common/pagination/CLAUDE.md`.

### Path 상수 (`common/const/path_consts.py`)

```python
PUBLIC_FOLDER_PATH = ...   # static files 디렉토리
```

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

**driver phone OTP**: SMTP 대신 SMS gateway. `common/sms/` 폴더에 별도 추가 권장 (현재 미구현). `auth/service.py` 의 OTP 메서드가 (이메일 / 폰) 분기 호출.

---

## 7. Base Model (`common/model/base_model.py`)

```python
@as_declarative()
class Base:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
```

### 모든 모델은 반드시

1. `Base` 상속
2. `__tablename__` 명시 (snake_case 단수형 — TMS 관행. ste 는 복수형이었으나 tms 는 alembic 자동생성 + 도메인명 일치 위해 단수)
3. `common/model/models_registry.py` 에 import 추가

### 감사 필드 (`created_by_user_id` / `updated_by_user_id`)

**자동 채움 없음.** 서비스 레이어에서 수동 설정:

```python
do = DeliveryOrderModel(
    ...,
    created_by_user_id=actor_user_id,
    updated_by_user_id=actor_user_id,
)
# update 시:
do.updated_by_user_id = actor_user_id
```

`updated_at` 만 `onupdate=func.now()` 로 자동 갱신.

### Soft Delete

- 마스터 / 트랜잭션 데이터는 `is_active=False` 로 논리 삭제
- 하드 삭제는 FK `ondelete="RESTRICT"` 로 차단 (orphan 방지)
- **모든 read 쿼리는 `.where(Model.is_active.is_(True))` 명시 적용** — 자동 필터 없음
- 예외: append-only 도메인 (`chassis_event`, `location_ping`) 는 삭제 없음 (`is_active` 컬럼은 있지만 사용 안 함)

---

## 8. TeamScopedMixin (`common/model/team_scoped_mixin.py`)

⭐ **팀 scoped 모델의 기본 인프라.** 모든 비즈니스 도메인 모델은 `(Base, TeamScopedMixin)` 이중 상속이 기본값. 예외는 글로벌 모델 (`User` / `Team` / `UserTeam` 조인 / `Permission` 마스터 / `FileAsset` 폴리모픽).

```python
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin

class DeliveryOrderModel(Base, TeamScopedMixin):
    __tablename__ = "delivery_order"
    bl_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # ...
```

자동 추가:
- `team_id: Mapped[int]` — `FK → teams.id ondelete="CASCADE"`, `index=True`, `nullable=False`
- `team` relationship — `lazy="selectin"` (⚠️ `ORM_LAZY_DEFAULT="raise"` 예외 — N+1 주의)

### `__with_team_rel__ = False` — 라인 / 이벤트 테이블 예외

헤더-라인 구조에서 **라인 쪽** 은 `.team` 관계를 헤더 통해 접근하므로 라인에 `.team` 이 또 있으면 충돌/중복 로드 유발. 라인 테이블엔 `__with_team_rel__ = False` 를 명시:

```python
class ContainerModel(Base, TeamScopedMixin):
    __tablename__ = "container"
    __with_team_rel__ = False              # ← .team 제거, 헤더 통해 접근
    delivery_order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # ...
```

### 복합 FK + UniqueConstraint 패턴 (같은 도메인 내부 라인)

같은 도메인 / 비즈니스 묶음 안의 라인 테이블은 헤더에 복합 FK:

```python
__table_args__ = (
    UniqueConstraint("team_id", "id", name="uq_container_team_id_id"),
    ForeignKeyConstraint(
        ["team_id", "delivery_order_id"],
        ["delivery_order.team_id", "delivery_order.id"],
        ondelete="CASCADE",
        name="fk_container_delivery_order_team_id_id",
    ),
    Index("ix_container_team_id_id", "team_id", "id"),
    Index("ix_container_team_do", "team_id", "delivery_order_id"),
)
```

### 도메인 간 FK (단순 FK + ondelete 분기)

```python
# delivery_order.model
customer_id: Mapped[int] = mapped_column(
    ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False,
)
terminal_id: Mapped[int | None] = mapped_column(
    ForeignKey("terminal.id", ondelete="SET NULL"), nullable=True,
)
vessel_id: Mapped[int | None] = mapped_column(
    ForeignKey("vessel.id", ondelete="SET NULL"), nullable=True,
)
```

| 비즈니스 의미 | `ondelete` |
| --- | --- |
| 절대 삭제 막아야 함 (참조 보호) | `RESTRICT` |
| 삭제되어도 OK, 참조만 끊김 | `SET NULL` |
| 부모 삭제 시 자식 정리 (같은 도메인 안 라인) | `CASCADE` |

### 인덱스 — team_id leftmost

```python
Index("ix_<table>_team_id_id",   "team_id", "id"),
Index("ix_<table>_team_<field>", "team_id", "<field>"),
```

**모든 복합 인덱스는 `team_id` 가 첫 컬럼**. 팀 scoped 쿼리 (`WHERE team_id = ? ...`) 의 leftmost prefix 로 B-tree 효율 극대화.

### Relationship — primaryjoin 에 team_id 포함

```python
# 헤더 → 라인
containers = relationship(
    "ContainerModel",
    back_populates="delivery_order",
    cascade="all, delete-orphan",
    lazy=settings.ORM_LAZY_DEFAULT,
    order_by="ContainerModel.id.asc()",
    primaryjoin=lambda: and_(
        foreign(ContainerModel.team_id) == DeliveryOrderModel.team_id,
        foreign(ContainerModel.delivery_order_id) == DeliveryOrderModel.id,
    ),
    passive_deletes=True,
)

# 라인 → 헤더
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

세부 (viewonly, 폴리모픽 파일, updated_by 관계, 순환 참조 회피) 는 `src/team/CLAUDE.md` §1-7 참조.

### 팀 scoped 테이블 목록 수집 헬퍼

```python
from common.model.team_scoped_mixin import get_team_scoped_table_names

names = get_team_scoped_table_names()
# → ["delivery_order", "container", "leg", "api_key", "customer", ...]
```

런타임에 metadata 에서 자동 수집. 시스템 배치 작업이나 진단용.

---

## 9. models_registry.py

모든 모델은 여기에 import 해야 Alembic autogenerate 가 감지한다.

```python
from common.model.base_model import Base

# 글로벌 마스터
from user.model import UserModel
from team.model import TeamModel, UserTeamModel
from rbac.model import PermissionModel, PermissionGroupModel, PermissionGroupPermission
from file.model import FileAssetModel
from api_key.model import ApiKeyModel
from invite.model import InviteModel

# 비즈니스 마스터
from customer.model import CustomerModel
from terminal.model import TerminalModel
from vessel.model import VesselModel
from location.model import LocationModel
from driver.model import DriverModel
from truck.model import TruckModel
from chassis.model import ChassisModel
from equipment_pool.model import EquipmentPoolModel

# D/O / Container / Leg
from delivery_order.model import DeliveryOrderModel
from container.model import ContainerModel, ContainerEventModel
from container_stop.model import ContainerStopModel
from chassis_event.model import ChassisEventModel
from leg.model import LegModel
from leg_stop.model import LegStopModel
from leg_layer.model import LegAddonModel
from leg_driver_segment.model import LegDriverSegmentModel
from load_type_template.model import LoadTypeTemplateModel, LoadTypeTemplateStepModel
from street_turn.model import StreetTurnModel
from dual_transaction.model import DualTransactionModel

# Rate (재설계) — 요율 서브시스템
from charge_code.model import ChargeCodeModel
from rate_point.model import RatePointModel
from rate_zone.model import RateZoneModel, RateZoneMemberModel
from rate_group.model import RateGroupModel
from rate_sheet.model import RateSheetModel, RateEntryModel, RateEntryHistoryModel
from rate_multiplier.model import RateMultiplierModel
from driver_rate_assignment.model import DriverRateAssignmentModel
from accessorial.model import AccessorialModel

# Settlement / Invoice (재설계)
from payroll.model import PayrollSettlementModel, PayrollLineModel, PayrollChargeModel
from invoice.model import InvoiceModel, InvoiceLineModel
from audit_log.model import AuditLogModel

# Mobile / Realtime
from location_ping.model import LocationPingModel
from push_token.model import PushTokenModel
from notification.model import NotificationModel

# AI
from ai_intake.model import AiIntakeModel
```

새 모델 추가 시 반드시 이 파일 수정 → `alembic revision --autogenerate -m "add <model>"`.

---

## 10. Lifecycle (`common/lifecycle/lifespan.py`)

FastAPI `lifespan` context manager 가 startup/shutdown 처리:

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

도메인 코드는 **DB / Redis / MinIO 재초기화 금지**. 글로벌 세션이나 커넥션 풀 만들지 말고 반드시 dependency 주입 사용.

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
- POST / PATCH / DELETE → `get_write_db`
- **Service / Repository 에서는 `commit()` 호출 금지** — yield 후 auto-commit 만 신뢰
- Repository write 메서드는 `await db.flush()` + 필요 시 `await db.refresh(obj)`

### Timed Session

`TimedAsyncSession` 이 모든 `execute()` 를 `asyncio.wait_for` 로 래핑:
- SELECT → 30초 (`DB_READ_TIMEOUT`)
- INSERT / UPDATE / DELETE → 600초 (`DB_WRITE_TIMEOUT`)

초과 시 `asyncio.TimeoutError` → 전역 핸들러가 504 로 변환.

---

## 12. Cache Dependencies (`cache/`)

```python
async def get_write_redis() -> Redis:   # SET / DEL / INCR
async def get_read_redis() -> Redis:    # GET / EXISTS / TTL
async def get_redis_client() -> RedisClient:   # 읽기/쓰기 분리 래퍼
async def get_redis() -> Redis:         # write_redis 별칭
```

- 커넥션 풀: read=50, write=10 (read-heavy 가정)
- AWS ElastiCache TLS 는 `REDIS_SSL=True` 로 활성화
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

**규약**: 유틸은 순수 함수로. stdlib (`datetime`, `json`, `secrets`) 이나 검증된 라이브러리 (`cryptography`) 로 해결 가능한 건 재구현 금지.

---

## 14. 알려진 상태 (정보 공유)

- `common/service/` 폴더는 현재 비어있음 — cross-domain orchestration service 가 필요해질 때 채울 자리
- `database/event_hooks.py` 가 비어있어 감사 필드는 수동 채움 (Base Model 섹션 참조)
- `permission_guard`, `team_admin_guard` dependency 는 활성 사용 중 (ste 와 달리 tms 는 다수 라우터에 부착)
- `rate_limit` dependency 는 정의만 있고 현재 라우터에서 미사용 (외부 API Key 호출 노출 시 활성화 예정)
- `delay.py` (`DelayMiddleware`) 는 네트워크 지연 시뮬레이션. 기본 비활성, 디버깅 시만

---

## 15. 관련 문서

- [`../CLAUDE.md`](../CLAUDE.md) — 루트 헌법
- [`pagination/CLAUDE.md`](./pagination/CLAUDE.md) — 페이지네이션 / DELETE / WS / sync
- [`repository/CLAUDE.md`](./repository/CLAUDE.md) — TeamScopedRepoMixin
- [`../team/CLAUDE.md`](../team/CLAUDE.md) — 표준 도메인 레퍼런스
- [`../auth/CLAUDE.md`](../auth/CLAUDE.md) — 인증 가드 / JWT / OTP
- [`../rbac/CLAUDE.md`](../rbac/CLAUDE.md) — 권한 / role 가드
- [`../delivery_order/CLAUDE.md`](../delivery_order/CLAUDE.md) — TMS 대표 도메인
- [`../driver_mobile/CLAUDE.md`](../driver_mobile/CLAUDE.md) — BFF / 모바일 라우팅
