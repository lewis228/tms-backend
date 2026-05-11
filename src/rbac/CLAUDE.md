# src/rbac/CLAUDE.md

권한 모델 (Permission / PermissionGroup / PermissionGroupPermission) + 2단 Redis 캐시 + **RolesEnum + role 가드** (TMS 신규).

**현재 상태**: 인프라 완비 + `permission_guard` 활성 사용 (대부분 mutation 라우터에 부착). driver 모바일 앱 진입과 함께 `RolesEnum` 도입 — role 단위 빠른 가드.

---

## 1. 모델 구조 (ste 그대로)

### PermissionModel

전역 권한 정의 (팀에 독립). 마스터 데이터.

```python
class PermissionModel(Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(100), unique=True)   # "DO_WRITE"
    label: Mapped[str] = mapped_column(String(200))               # "Delivery Order Write"
    category: Mapped[str] = mapped_column(String(50))             # "delivery_order"
    description: Mapped[Optional[str]]
```

### PermissionGroupModel

**팀별** 권한 그룹. 팀당 ADMIN / MEMBER / VIEWER 3개의 system group + 커스텀 그룹.

```python
class PermissionGroupModel(Base, TeamScopedMixin):
    __tablename__ = "permission_groups"
    name: Mapped[str]
    is_admin: Mapped[bool] = mapped_column(default=False)         # True면 모든 권한 바이패스
    is_system: Mapped[bool] = mapped_column(default=False)        # ADMIN/MEMBER/VIEWER 기본
    system_key: Mapped[Optional[str]]                              # "ADMIN" | "MEMBER" | "VIEWER"
    version: Mapped[int] = mapped_column(default=1)               # 권한 변경 시 +1 (캐시 무효화)
    excluded_attribute_ids: Mapped[Optional[list]]                # JSON, 속성 레벨 제외
    permissions = relationship(...)
    user_teams = relationship(...)
```

### PermissionGroupPermission

Join 테이블 — 그룹 ↔ 권한.

```python
class PermissionGroupPermission(Base, TeamScopedMixin):
    __tablename__ = "permission_group_permissions"
    __table_args__ = (UniqueConstraint("team_id", "permission_group_id", "permission_id"),)
    permission_group_id: ForeignKey("permission_groups.id")
    permission_id: ForeignKey("permissions.id")
```

`TeamScopedMixin` 덕에 `team_id` 자동으로 포함 — CASCADE 로 팀 삭제 시 정리.

---

## 2. 권한 코드

### 정의 위치

```python
# rbac/const/const.py

# Team / Member
TEAM_RENAME = "TEAM_RENAME"
TEAM_DELETE = "TEAM_DELETE"
TEAM_MEMBER_INVITE = "TEAM_MEMBER_INVITE"
TEAM_MEMBER_REMOVE = "TEAM_MEMBER_REMOVE"
TEAM_MEMBER_ROLE_WRITE = "TEAM_MEMBER_ROLE_WRITE"
TEAM_MEMBER_PERMISSION_ASSIGN = "TEAM_MEMBER_PERMISSION_ASSIGN"

# Delivery Order
DO_READ = "DO_READ"
DO_WRITE = "DO_WRITE"
DO_DISPATCH = "DO_DISPATCH"
DO_COMPLETE = "DO_COMPLETE"
DO_CANCEL = "DO_CANCEL"

# Leg / Dispatch
LEG_READ = "LEG_READ"
LEG_WRITE = "LEG_WRITE"
LEG_ASSIGN_DRIVER = "LEG_ASSIGN_DRIVER"

# Settlement
SETTLEMENT_READ = "SETTLEMENT_READ"
SETTLEMENT_WRITE = "SETTLEMENT_WRITE"
SETTLEMENT_APPROVE = "SETTLEMENT_APPROVE"

# Master Data
CUSTOMER_READ = "CUSTOMER_READ"
CUSTOMER_WRITE = "CUSTOMER_WRITE"
DRIVER_READ = "DRIVER_READ"
DRIVER_WRITE = "DRIVER_WRITE"
TRUCK_WRITE = "TRUCK_WRITE"
# ...

# Rate / Settlement
RATE_WRITE = "RATE_WRITE"
RATE_TARIFF_WRITE = "RATE_TARIFF_WRITE"

# API Key
API_KEY_READ = "API_KEY_READ"
API_KEY_WRITE = "API_KEY_WRITE"
```

### 네이밍 규약

`CONSTANT_CASE` + 도메인 prefix + 동작 동사.

- `TEAM_*` — 팀 관리
- `DO_*` — Delivery Order
- `LEG_*` — Leg / Dispatch
- `SETTLEMENT_*` — 정산
- `<MASTER>_*` — Customer, Driver, Truck, Vessel 등 마스터
- `API_KEY_*` — API 키 관리

### 새 권한 추가 절차

1. `rbac/const/const.py` 에 상수 정의
2. `ALL_PERMISSION_CODES` 리스트에 추가
3. 기본 그룹 매핑 업데이트 (`DEFAULT_ADMIN_CODES`, `DEFAULT_DISPATCHER_CODES`, `DEFAULT_VIEWER_CODES`)
4. `GROUP_DEFAULTS_BY_SYSTEM_KEY` 가 자동으로 참조
5. 마이그레이션 생성 — `permissions` 테이블에 새 row seed
6. 라우터에 `permission_guard("NEW_CODE")` 적용

### 시스템 그룹 기본값 (TMS — ADMIN/DISPATCHER/VIEWER)

```python
GROUP_DEFAULTS_BY_SYSTEM_KEY = {
    "ADMIN":      DEFAULT_ADMIN_CODES,       # 전체 권한 또는 is_admin=True
    "DISPATCHER": DEFAULT_DISPATCHER_CODES,  # D/O 생성/디스패치/leg 할당 가능
    "VIEWER":     DEFAULT_VIEWER_CODES,      # 읽기만
}
```

> **TMS 차이**: ste 는 ADMIN/MEMBER/VIEWER. TMS 는 DISPATCHER 가 핵심 역할 (운송 디스패치 담당) → MEMBER 대신 DISPATCHER.

---

## 3. RolesEnum + role 가드 ⭐ TMS 신규

### 왜 추가됐나

- `permission_guard` 는 RBAC 코드 단위 (세밀한 권한 제어)
- 그러나 **모바일 앱 (driver)** 처럼 "이 라우터는 driver 만 호출" 같은 큰 단위 가드는 RBAC 보다 role 가드가 더 직관적
- driver 가 dispatcher 권한 코드를 가질 일이 없고, role 이 곧 user category

### RolesEnum 정의

```python
# user/const/roles.py
from enum import Enum

class RolesEnum(str, Enum):
    ADMIN = "ADMIN"
    DISPATCHER = "DISPATCHER"
    DRIVER = "DRIVER"
    CUSTOMER = "CUSTOMER"     # (옵션 — 향후 화주 셀프 포털)
    VIEWER = "VIEWER"
```

- `user.role` 컬럼 — 글로벌 user 의 기본 role
- 또는 `user_team.role` — 팀별 role (한 user 가 팀마다 다른 role)

> **결정**: TMS 는 **팀별 role** (`UserTeamModel.role`) — 한 user 가 dispatcher 로 가입한 팀도 있고 driver 로 가입한 팀도 있을 수 있음.

### role 가드 — `require_driver`, `require_dispatcher` 등

```python
# user/dependencies/role_guards.py
def make_role_guard(*allowed_roles: RolesEnum):
    async def guard(
        request: Request,
        me: UserResponseSchema = Depends(get_current_user),
    ) -> UserResponseSchema:
        role = _resolve_user_role(request, me)   # X-Team-Id 헤더 → user_team.role
        if role not in [r.value for r in allowed_roles]:
            raise AppException(
                code="FORBIDDEN_ROLE",
                message=f"{[r.value for r in allowed_roles]} 만 호출 가능.",
                status_code=403,
            )
        return me
    return guard


require_admin = make_role_guard(RolesEnum.ADMIN)
require_dispatcher = make_role_guard(RolesEnum.ADMIN, RolesEnum.DISPATCHER)
require_driver = make_role_guard(RolesEnum.DRIVER)
```

> 현재 driver_mobile/router.py 의 `require_driver` 가 인라인 정의. 점진적으로 `user/dependencies/role_guards.py` 로 이동 권장.

### 라우터 사용

```python
# driver_mobile/router.py
@router.get("/tasks/today", response_model=TodayTasksResponse)
async def tasks_today(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),   # ← role 가드
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    ...
```

### `permission_guard` vs role 가드 선택

| 케이스 | 어느 가드 |
| --- | --- |
| "이 라우터는 driver 만" | `require_driver` (role) |
| "이 라우터는 admin / dispatcher 만" | `require_dispatcher` (role) |
| "이 작업은 LEG_ASSIGN 권한 필요" | `permission_guard("LEG_ASSIGN_DRIVER")` (RBAC code) |
| "이 작업은 admin 만 + LEG_WRITE 코드 보유" | 두 개 동시 부착 |
| Driver 본인의 leg 인지 검증 | service 안에서 `if leg.assigned_driver_id != me.id: raise Forbidden` |

**가이드**: 모바일 앱 / 큰 카테고리는 role, 비즈니스 권한 (특정 액션 가능 여부) 은 RBAC code.

---

## 4. `permission_guard` dependency

### 시그니처

```python
# rbac/dependencies/guards.py
def permission_guard(*required_codes: str):
    """required 중 하나라도 가지고 있으면 통과 (OR 논리)."""
    async def guard(
        request: Request,
        me: UserResponseSchema = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        redis: Redis = Depends(get_redis),
    ):
        ...
    return guard
```

### 동작

1. `_extract_team_id(request)` — path param → query → `X-Team-Id` 헤더 순으로 찾음
2. `RbacRepository.get_user_perm_meta()` — 유저의 그룹 codes + is_admin 조회 (캐시 경유)
3. `is_admin_group=True` → 즉시 통과
4. `team_id` 없거나 유저가 그 팀에 소속 아님 → 403 `TEAM_REQUIRED`
5. required 와 codes 교집합 없음 → 403 `PERMISSION_DENIED` + `{"missing": [...]}`

### 라우터 적용 패턴 (TMS — 분리 사용)

```python
@router.post("/{do_id}/dispatch", response_model=DOResponseSchema)
async def dispatch_do(
    do_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_DISPATCH)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DeliveryOrderService(db, team_id, redis=redis).dispatch(
        do_id, actor_user_id=int(me.id),
    )
```

> ⚠️ **STE 와 다른 점**:
> - ste 는 `dependencies=[Depends(permission_guard("..."))]` (라우터 데코레이터 인자)
> - tms 는 `_2: None = Depends(permission_guard(...))` (함수 시그니처)
> - 둘 다 작동하지만 tms 는 일관성 위해 함수 시그니처 방식 통일

### OR vs AND

```python
permission_guard("DO_READ", "DO_ADMIN")           # OR — 둘 중 하나
```

AND 가 필요하면 두 개 부착:

```python
_2: None = Depends(permission_guard(DO_WRITE)),
_3: None = Depends(permission_guard(LEG_ASSIGN_DRIVER)),
```

### `team_admin_guard`

권한 코드와 무관하게 **그룹이 admin (`is_admin=True`) 인지만** 확인. 그룹/권한 관리 엔드포인트에서 사용:

```python
_2: None = Depends(team_admin_guard),
```

---

## 5. 2단 Redis 캐시 (`cache_service.py`)

**도메인 코드가 `permission_group_permissions` 테이블을 직접 쿼리하는 것을 금지한다.** 항상 `RbacRepository.get_user_perm_meta()` 로 접근 → 캐시 자동 활용.

### Level 1 — 유저의 팀 메타

| 항목 | 값 |
| --- | --- |
| 키 | `rbac:ut:{user_id}:{team_id}` |
| 값 | `{"gid": group_id, "ver": version, "adm": is_admin, "role": "DISPATCHER"}` JSON |
| TTL | `RBAC_USER_TEAM_TTL=300` (5분) |

> **TMS 추가**: `role` 필드 — RolesEnum 값. role 가드가 이 캐시 활용.

### Level 2 — 그룹의 권한 코드

| 항목 | 값 |
| --- | --- |
| 키 | `rbac:gc:{group_id}:v{version}` |
| 값 | `["DO_READ", "DO_WRITE", ...]` JSON |
| TTL | `RBAC_GROUP_CODES_TTL=300` |

**버전이 키의 일부**. 그룹.version 을 +1 하면 기존 키는 자연 만료되고, 다음 조회는 `v{new_version}` 키로 간다.

### 캐시 무효화 트리거

다음 경우 **반드시** `PermissionGroupModel.version += 1` 실행:
- 그룹에 권한 추가/제거
- 그룹 메타데이터 변경 (is_admin 토글 등)
- 유저가 그룹 간 이동할 때 → 그룹 version 은 그대로, `rbac:ut:{user_id}:{team_id}` 키를 delete
- **유저의 role 변경 시** → `rbac:ut:{user_id}:{team_id}` 키 delete

조회 경로:
```
RbacRepository.get_user_perm_meta(user_id, team_id):
    1. rbac:ut:{user_id}:{team_id} 조회 → miss 면 DB 로 user-team → 그룹 id/version/is_admin + role 확인 → 캐시 set
    2. is_admin=True 면 codes=[] 반환 (guard 가 바이패스)
    3. rbac:gc:{group_id}:v{version} 조회 → miss 면 DB 로 permission codes 조회 → 캐시 set
    4. return (codes, group_id, version, is_admin, role)
```

---

## 6. Repository / Service

### RbacRepository

```python
class RbacRepository:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = RbacCacheService(redis)
```

- **항상 redis 도 주입받는다** — 캐시 경유 없는 직접 쿼리를 막기 위함.
- 주 메서드: `get_user_perm_meta(user_id, team_id) -> (codes, group_id, version, is_admin, role)`

### RbacService

그룹 / 권한 / role 관리 엔드포인트 (CRUD).

---

## 7. 라우터

`/api/v1/rbac/` 하위. 주요 엔드포인트:
- `GET /groups` — 팀의 권한 그룹 목록
- `POST /groups` — 그룹 생성
- `PATCH /groups/{id}` — 그룹 권한 수정 (version +1)
- `DELETE /groups/{id}` — 그룹 삭제
- `POST /groups/{id}/members` — 그룹에 멤버 추가
- `DELETE /groups/{id}/members/{user_id}` — 멤버 제거

그룹/권한 변경 메서드는 **반드시 마지막에 `group.version += 1`** 수행.

### 새 엔드포인트 추가 패턴

```python
@router.post(
    "/groups",
    response_model=PermissionGroupResponseSchema,
    status_code=201,
)
async def create_permission_group(
    body: CreatePermissionGroupRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(TEAM_MEMBER_PERMISSION_ASSIGN)),
    team_id: int = Depends(get_team_scope),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    return await RbacService(db, team_id).create_group(body, actor_id=int(me.id))
```

---

## 8. 도메인 엔드포인트에 권한 가드 붙이는 실무 가이드

### 언제 `permission_guard` 를 쓰나

- 리소스 쓰기 작업 — 모든 mutation 라우터에 코드 부착이 TMS 기본
- "이 코드가 있어야만 가능" 한 액션 (디스패치 / 정산 / 권한 할당)

### 언제 role 가드를 쓰나

- 모바일 앱 (`driver_mobile/`) 의 모든 엔드포인트 — `require_driver`
- 관리 화면 — `require_admin` 또는 `require_dispatcher`
- 카테고리 단위 가드 — RBAC code 까지 가지 않아도 되는 경우

### 활성화 순서 (새 권한)

1. `rbac/const/const.py` 에 코드 정의
2. 마이그레이션으로 `permissions` row seed
3. `DEFAULT_*_CODES` 에 할당 (어느 시스템 그룹이 기본 보유?)
4. 라우터에 `_2: None = Depends(permission_guard("..."))` 추가
5. 기존 유저들은 **자동으로 시스템 그룹의 기본 codes 를 받지 않는다** — 필요시 마이그레이션으로 역-populate

---

## 9. 알려진 상태

- `permission_guard` 활성 사용 (대부분 mutation 라우터 부착)
- `team_admin_guard` 일부 라우터 사용 (그룹 관리)
- `RolesEnum` 추가됨 — driver_mobile 에서 사용 시작. 다른 도메인도 점진적 도입
- 권한 로그/감사 엔드포인트 없음. "누가 언제 무슨 권한으로 무엇을 했는가" 는 `created_by_user_id` + access log 기반으로만 추적
- `excluded_attribute_ids` (속성 레벨 배제) — JSON 컬럼 존재하나 현재 엔포스먼트 로직 없음. 향후 필드 레벨 권한 확장용 스캐폴딩

---

## 10. 관련 문서

- [`../auth/CLAUDE.md`](../auth/CLAUDE.md) — `access_token`, JWT, OTP
- [`../user/CLAUDE.md`](../user/CLAUDE.md) (있다면) — `RolesEnum`, `get_current_user`
- [`../driver_mobile/CLAUDE.md`](../driver_mobile/CLAUDE.md) — `require_driver` 사용 예
- [`../team/CLAUDE.md`](../team/CLAUDE.md) — Depends 순서 / 표준 도메인 규약
