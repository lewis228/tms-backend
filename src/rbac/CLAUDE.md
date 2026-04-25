# src/rbac/CLAUDE.md

권한 모델 (Permission / PermissionGroup / PermissionGroupPermission) + 2단 Redis 캐시.

**현재 상태**: 인프라는 완비. `permission_guard` dependency는 정의돼 있으나 라우터에서 아직 활성 사용처가 없다. 새 권한이 필요한 엔드포인트를 만들 때 이 파일의 규약대로 활성화한다.

---

## 1. 모델 구조

### PermissionModel

전역 권한 정의 (팀에 독립). 마스터 데이터.

```python
class PermissionModel(Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(100), unique=True)   # "TEAM_RENAME"
    label: Mapped[str] = mapped_column(String(200))               # "Team Rename"
    category: Mapped[str] = mapped_column(String(50))             # "team"
    description: Mapped[Optional[str]]
```

### PermissionGroupModel

**팀별** 권한 그룹. 팀당 ADMIN/MEMBER/VIEWER 3개의 system group + 커스텀 그룹.

```python
class PermissionGroupModel(Base, TeamScopedMixin):
    __tablename__ = "permission_groups"
    name: Mapped[str]
    is_admin: Mapped[bool] = mapped_column(default=False)         # True면 모든 권한 바이패스
    is_system: Mapped[bool] = mapped_column(default=False)        # ADMIN/MEMBER/VIEWER 기본
    system_key: Mapped[Optional[str]]                              # "ADMIN"|"MEMBER"|"VIEWER"
    version: Mapped[int] = mapped_column(default=1)               # 권한 변경 시 +1 (캐시 무효화)
    excluded_attribute_ids: Mapped[Optional[list]]                # JSON, 속성 레벨 제외
    permissions = relationship(...)                               # many-to-many
    user_teams = relationship(...)                                 # 그룹에 속한 유저-팀
```

### PermissionGroupPermission

Join 테이블 — 그룹 ↔ 권한.

```python
class PermissionGroupPermission(Base, TeamScopedMixin):
    __tablename__ = "permission_group_permissions"
    __table_args__ = (UniqueConstraint("team_id", "group_id", "permission_id"),)
    group_id: ForeignKey("permission_groups.id")
    permission_id: ForeignKey("permissions.id")
```

`TeamScopedMixin` 덕에 `team_id` 자동으로 포함 — CASCADE로 팀 삭제 시 정리.

---

## 2. 권한 코드

### 정의 위치

```python
# rbac/const/const.py
TEAM_RENAME = "TEAM_RENAME"
TEAM_DELETE = "TEAM_DELETE"
TEAM_MEMBER_INVITE = "TEAM_MEMBER_INVITE"
TEAM_MEMBER_REMOVE = "TEAM_MEMBER_REMOVE"
TEAM_MEMBER_ROLE_WRITE = "TEAM_MEMBER_ROLE_WRITE"
TEAM_MEMBER_PERMISSION_ASSIGN = "TEAM_MEMBER_PERMISSION_ASSIGN"
```

### 네이밍 규약

`CONSTANT_CASE` + 도메인 prefix + 동작 동사.

- `TEAM_*` — 팀 관리
- `OCEAN_SHIPMENT_*`, `OCEAN_CONTAINER_*` 등 — 해상 운송
- `API_KEY_*` — API 키 관리

### 새 권한 추가 절차

1. `rbac/const/const.py`에 상수 정의
2. `ALL_PERMISSION_CODES` 리스트에 추가
3. 기본 그룹 매핑 업데이트 (`DEFAULT_ADMIN_CODES`, `DEFAULT_MEMBER_CODES`, `DEFAULT_VIEWER_CODES`)
4. `GROUP_DEFAULTS_BY_SYSTEM_KEY`가 자동으로 참조
5. 마이그레이션 생성 — `permissions` 테이블에 새 row seed
6. 라우터에 `permission_guard("NEW_CODE")` 적용

### 시스템 그룹 기본값

```python
GROUP_DEFAULTS_BY_SYSTEM_KEY = {
    "ADMIN":  DEFAULT_ADMIN_CODES,   # 전체 권한 (또는 is_admin=True)
    "MEMBER": DEFAULT_MEMBER_CODES,  # 제한적
    "VIEWER": DEFAULT_VIEWER_CODES,  # 읽기만
}
```

---

## 3. `permission_guard` dependency

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
5. required와 codes 교집합 없음 → 403 `PERMISSION_DENIED` + `{"missing": [...]}`

### 라우터 적용 패턴

```python
@router.post(
    "/{team_id}/shipments/{shipment_id}/approve",
    response_model=ShipmentResponseSchema,
    dependencies=[Depends(permission_guard("OCEAN_SHIPMENT_WRITE"))],
)
async def approve_shipment(
    team_id: int,
    shipment_id: int,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    ...
```

`dependencies=[...]` 리스트에 넣으면 함수 시그니처에 등장하지 않아도 실행된다 (반환값 안 씀).

### OR vs AND

- `permission_guard("A", "B")` = A **또는** B 보유 시 통과
- AND가 필요하면 두 개를 나란히: `dependencies=[Depends(permission_guard("A")), Depends(permission_guard("B"))]`

### `team_admin_guard`

권한 코드와 무관하게 **그룹이 admin(`is_admin=True`)인지만** 확인. 그룹/권한 관리 엔드포인트에서 사용할 법한 유틸.

---

## 4. 2단 Redis 캐시 (`cache_service.py`)

**도메인 코드가 `permission_group_permissions` 테이블을 직접 쿼리하는 것을 금지한다.** 항상 `RbacRepository.get_user_perm_meta()`로 접근 → 캐시 자동 활용.

### Level 1 — 유저의 팀 메타

| 항목 | 값 |
| --- | --- |
| 키 | `rbac:ut:{user_id}:{team_id}` |
| 값 | `{"gid": group_id, "ver": version, "adm": is_admin}` JSON |
| TTL | `RBAC_USER_TEAM_TTL=300` (5분) |

히트율 매우 높음 — 로그인 1회, 요청 여러 번.

### Level 2 — 그룹의 권한 코드

| 항목 | 값 |
| --- | --- |
| 키 | `rbac:gc:{group_id}:v{version}` |
| 값 | `["TEAM_RENAME", "TEAM_DELETE", ...]` JSON |
| TTL | `RBAC_GROUP_CODES_TTL=300` |

**버전이 키의 일부**. 그룹.version을 +1 하면 기존 키는 자연 만료되고, 다음 조회는 `v{new_version}` 키로 간다.

### 캐시 무효화 트리거

다음 경우 **반드시** `PermissionGroupModel.version += 1` 실행:
- 그룹에 권한 추가/제거
- 그룹 메타데이터 변경 (is_admin 토글 등)
- 유저가 그룹 간 이동할 때 → 그룹 version은 그대로, `rbac:ut:{user_id}:{team_id}` 키를 delete

조회 경로:
```
RbacRepository.get_user_perm_meta(user_id, team_id):
    1. rbac:ut:{user_id}:{team_id} 조회 → miss면 DB로 유저-팀 → 그룹 id/version/is_admin 확인 → 캐시 set
    2. is_admin=True면 codes=[] 반환 (guard가 바이패스)
    3. rbac:gc:{group_id}:v{version} 조회 → miss면 DB로 permission codes 조회 → 캐시 set
    4. return (codes, group_id, version, is_admin)
```

---

## 5. Repository / Service

### RbacRepository

```python
class RbacRepository:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.cache = RbacCacheService(redis)
```

- **항상 redis도 주입받는다** — 캐시 경유 없는 직접 쿼리를 막기 위함.
- 주 메서드: `get_user_perm_meta(user_id, team_id) -> (codes, group_id, version, is_admin)`

### RbacService

현재 stub. 그룹/권한 관리 엔드포인트(CRUD)가 추가되면 여기 로직이 늘어난다.

---

## 6. 라우터

`/api/v1/rbac/`. 현재 엔드포인트는 제한적. 새 엔드포인트 추가 시:

```python
@router.post(
    "/groups",
    response_model=PermissionGroupResponseSchema,
    status_code=201,
    dependencies=[Depends(permission_guard("TEAM_MEMBER_PERMISSION_ASSIGN"))],
)
async def create_permission_group(
    body: CreatePermissionGroupRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    svc = RbacService(db)
    return await svc.create_group(body, team_id=auth.team_id, actor_id=me.id)
```

그룹/권한 변경 메서드는 **반드시 마지막에 `group.version += 1`** 수행.

---

## 7. 도메인 엔드포인트에 권한 가드 붙이는 실무 가이드

### 언제 `permission_guard`를 쓰나

- 리소스 쓰기 작업 중 "일반 멤버는 불가, 특정 권한자만 가능"한 경우 (예: 팀 설정 변경, API 키 발급, 청구 관련 액션)
- 사용자가 많은 팀이 도입된 후부터 활성화 가치가 큼

### 언제 필요 없나

- 팀 스코프 검증만으로 충분한 경우 (예: "내 팀의 shipment 목록") → `jwt_or_api_key`가 이미 `X-Team-Id` 멤버십을 검증
- 개인 리소스 (예: `/user/me`) → 소유권이 곧 권한

### 활성화 순서

1. `rbac/const/const.py`에 코드 정의
2. 마이그레이션으로 `permissions` row seed
3. `DEFAULT_*_CODES`에 할당 (어느 시스템 그룹이 기본 보유?)
4. 라우터에 `dependencies=[Depends(permission_guard("..."))]` 추가
5. 기존 유저들은 **자동으로 시스템 그룹의 기본 codes를 받지 않는다** — 필요시 마이그레이션으로 역-populate

---

## 알려진 상태

- `permission_guard`, `team_admin_guard` 둘 다 정의만 있고 활성 라우터 0곳. 기능 자체는 동작.
- 권한 로그/감사 엔드포인트 없음. "누가 언제 무슨 권한으로 무엇을 했는가"는 `created_by_user_id` + access log 기반으로만 추적.
- `excluded_attribute_ids` (속성 레벨 배제) — JSON 컬럼 존재하나 현재 엔포스먼트 로직 없음. 향후 필드 레벨 권한 확장용 스캐폴딩.
