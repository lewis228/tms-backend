# src/auth/CLAUDE.md

인증 / 세션 / OAuth / OTP 담당. **TMS 의 인증 가드는 ste 보다 분리도가 높다** — `access_token` 과 `permission_guard` 를 각각 명시적으로 부착.

---

## 0. 라우터 인증 가드 — 분리 사용

| 가드 | 위치 | 동작 | 용도 |
| --- | --- | --- | --- |
| **`access_token`** | `auth/tokens/access_token.py` | JWT access token 만 허용 | 거의 모든 보호 엔드포인트 |
| **`refresh_token`** | `auth/tokens/refresh_token.py` | JWT refresh token 만 허용 | `/auth/token/access` 등 갱신 엔드포인트 |
| **`basic_token`** | `auth/tokens/basic_token.py` | HTTP Basic (email + 비밀번호) | `POST /auth/login` 만 |
| **`jwt_or_api_key`** | (필요 시 추가) | JWT 또는 API Key 허용 | 외부 개발자 통합 라우터 (현재 미사용) |

**TMS 패턴**:

```python
@router.post("", response_model=DOResponseSchema)
async def create_delivery_order(
    body: DeliveryOrderCreateRequest,
    _1: None = Depends(access_token),                       # 1. JWT 인증
    _2: None = Depends(permission_guard(DO_WRITE)),         # 2. 권한 체크
    team_id: int = Depends(get_team_scope),                 # 3. 팀 스코프
    db: AsyncSession = Depends(get_write_db),               # 4. DB
    me: UserResponseSchema = Depends(get_current_user),     # 5. 현재 유저
):
    ...
```

- `_1`, `_2` 식 sentinel 변수명 — dependency 가 raise 하면 끝. 결과 객체 안 받음.
- ste 와 다른 점: ste 는 `auth: AuthResult = Depends(jwt_or_api_key)` 한 줄, tms 는 두 줄 분리.
- WHY: API Key 호출자가 거의 없음 (대부분 admin/dispatcher 인증) + 권한 가드를 모든 mutation 에 부착하는 운영 정책.

### 가드 선택 표

| 케이스 | 가드 조합 |
| --- | --- |
| 로그인 (email + pw) | `basic_token` |
| OTP 발송 / 검증 | 인증 없음 (공개 — IP rate limit 또는 SMS 게이트웨이 자체 제한) |
| 비밀번호 재설정 | OTP 검증 후 OK 토큰만 |
| Refresh / Logout | `refresh_token` |
| 일반 사용자 read | `access_token` |
| 일반 사용자 write | `access_token` + `permission_guard(...)` |
| 외부 API Key 라우터 (현재 없음) | `jwt_or_api_key` (필요 시 추가) |
| Driver 앱 전용 | `access_token` + `require_driver` (role 체크) |
| Admin 전용 | `access_token` + `permission_guard("ADMIN_*")` 또는 `team_admin_guard` |

---

## 1. `access_token` — JWT 가드

### 동작

1. `Authorization: Bearer <jwt>` 헤더 확인 → 없으면 `UnauthorizedException`
2. JWT 디코드 (`AuthService.verify_token()`)
3. `token_type == "access"` 검증 (refresh 토큰 거부)
4. Redis 세션 / 디바이스 / 블랙리스트 검증 — 자세한 검증 흐름은 §3 참조
5. 사용자 로드 → `request.state.user` 세팅
6. dependency 결과: `None` (sentinel)

### 시그니처

```python
async def access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> None:
    ...
```

### 라우터 사용

```python
@router.get("/me", response_model=UserResponseSchema)
async def me(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(get_current_user),
):
    return me
```

---

## 2. `permission_guard` — RBAC 권한 체크 (활성)

### 시그니처

```python
def permission_guard(*required_codes: str):
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

1. `_extract_team_id(request)` — path → query → `X-Team-Id` 헤더 순으로 추출
2. `RbacRepository.get_user_perm_meta()` — 유저의 그룹 codes + is_admin (2단 Redis 캐시)
3. `is_admin=True` → 즉시 통과
4. team_id 없거나 유저가 그 팀에 미소속 → 403 `TEAM_REQUIRED`
5. `required_codes` 와 보유 codes 교집합 없음 → 403 `PERMISSION_DENIED` + `{"missing": [...]}`

### 라우터 사용

```python
@router.post("", response_model=DOResponseSchema)
async def create_do(
    body: DOCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),   # ← 권한 코드 명시
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    me: UserResponseSchema = Depends(get_current_user),
):
    ...
```

- `_1` / `_2` 가 dependency 캐시 깨지 않음 (FastAPI 자동 캐싱)
- 한 라우터에 여러 권한 (AND) 필요 시 `_2`, `_3` 식으로 누적

### OR 논리

```python
permission_guard("DO_READ", "DO_ADMIN")   # 둘 중 하나만 있어도 통과
```

### AND 논리

```python
@router.post("",
    response_model=DOResponseSchema,
    dependencies=[
        Depends(access_token),
        Depends(permission_guard("DO_WRITE")),
        Depends(permission_guard("DO_DISPATCH")),
    ],
)
```

세부 RBAC 규약은 `src/rbac/CLAUDE.md`.

---

## 3. JWT + Session 구조

### Token TTL

| 종류 | TTL | 설정 |
| --- | --- | --- |
| Access token | 30분 | `ACCESS_TTL=1800` |
| Refresh token | ~2.2시간 | `REFRESH_TTL=8000` |

### Redis 키 레이아웃

로그인 시 `AuthService._create_session()` 이 다음 키들을 모두 세팅 (TTL = `REFRESH_TTL`):

| 키 | 값 | 용도 |
| --- | --- | --- |
| `sess:{sid}` | `{"uid": int, "did": str}` JSON | 세션 메타데이터 |
| `refresh:{sid}` | 현재 refresh JWT 문자열 | rotation 검증 |
| `device:{did}:sid` | `sid` | 디바이스 → 세션 역인덱스 |
| `u:{uid}:sids` | Set of sid | 유저의 모든 세션 (전체 로그아웃용) |
| `bl:a:{jti}` | "1" | Access 토큰 블랙리스트 (선택적) |

### 디바이스 식별 (`did`)

- Web: `"web:{browser_id}"` where `browser_id` 는 httpOnly cookie 에 UUID 로 저장
- Driver App (iOS/Android): `"app:{uuid}"` — 앱 설치 시 device ID 발급
- Dispatcher App (옵션, 향후): `"app:dispatcher:{uuid}"`

쿠키가 사라지거나 디바이스가 바뀌면 `did` 가 바뀌어 기존 토큰이 무효화 (의도된 보안 동작 — `ACCOUNT_SWITCHED` 반환).

### 토큰 로테이션 (`AuthService.rotate_token`)

1. Refresh JWT 디코드 + 검증
2. `refresh:{sid}` 와 제출된 값 일치 확인 (불일치 = 재사용 감지)
3. 새 access 토큰 발급
4. `is_refresh=True` 면 refresh 토큰도 새로 발급하고 Redis 4개 키 전부 TTL 갱신

### 엔드포인트

| Method | Path | 용도 | 인증 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | 로그인 (email + 비밀번호) | `basic_token` |
| POST | `/api/v1/auth/token/access` | refresh → 새 access | refresh JWT |
| POST | `/api/v1/auth/token/refresh` | refresh 로테이션 | refresh JWT |
| POST | `/api/v1/auth/logout` | refresh cookie 제거 | 없음 |

Web 은 refresh 를 httpOnly cookie 로, App 은 body 로 내려준다. `settings.cookie_secure` 가 prod 에서 True.

---

## 4. OAuth (Web 전용)

### 구조

`auth/oauth/base.py` 의 추상 클래스 `OAuthProviderBase` 를 각 provider 가 상속.

```
auth/oauth/
├── base.py         # OAuthProviderBase, OAuthUserInfo
├── google.py       # GoogleOAuthProvider
├── kakao.py        # 추후 추가 시
└── apple.py        # 추후 추가 시
```

### 새 provider 추가 방법

1. `auth/oauth/{provider}.py` 에 `{Provider}OAuthProvider(OAuthProviderBase)` 작성
2. 8개 프로퍼티 구현: `provider`, `authorization_url`, `token_url`, `userinfo_url`, `client_id`, `client_secret`, `redirect_uri`, `scopes`
3. 2개 메서드 구현:
   - `async exchange_code_for_token(code) -> dict`
   - `async get_user_info(token_response) -> OAuthUserInfo`
4. `auth/router.py` 의 `_get_oauth_provider()` 에 분기 추가
5. `.env` 에 `{PROVIDER}_CLIENT_ID/SECRET/REDIRECT_URI` 추가 → `common/const/settings.py` 에 필드 추가

### 라우터 흐름

```
GET  /api/v1/auth/oauth/{provider}          → 302 → provider authorize URL
GET  /api/v1/auth/oauth/{provider}/callback → exchange code → oauth_login → 302 → frontend
```

Callback 라우터는 **예외 발생 시 frontend 의 `/login?error=oauth_failed` 로 redirect** — OAuth 는 redirect flow 라 JSON 에러를 반환할 수 없음. 유일하게 라우터 레벨에서 `try/except Exception` 을 감싸는 케이스.

### 모바일 앱

Driver 모바일 앱은 OAuth 안 씀 — **폰번호 + OTP 만**. OAuth 는 web (dispatcher / admin) 전용.

---

## 5. OTP — 두 가지 흐름

### 5-1. Email OTP (Web — 비밀번호 재설정 / 회원가입)

기존 ste 패턴 그대로:

| Step | Endpoint | Redis 키 | TTL |
| --- | --- | --- | --- |
| 1. 코드 요청 | `POST /auth/password/reset/request` | `otp:reset:{request_id}` = `{"email", "code", "tries": 0}` | 180초 |
| 2. 코드 검증 | `POST /auth/password/reset/verify` | `otp:ok:{request_id}` = email | 900초 |
| 3. 비밀번호 변경 | `POST /auth/password/reset/confirm` | — | — |

Signup 도 동일 (prefix 만 `otp:signup:` / `otp:signup_ok:`).

### 5-2. Phone OTP (Driver 앱 — 로그인) ⭐ TMS 신규

> **driver 앱 작업할 때 이 섹션 구현 필요.**

#### 흐름

```
1. POST /auth/driver/otp/request        body: {"phone": "+82-10-..."}
   → SMS 발송, otp:driver:{request_id} = {"phone", "code", "tries": 0}, TTL 180s
   → response: {"request_id": "..."}

2. POST /auth/driver/otp/verify         body: {"request_id": "...", "code": "123456"}
   → otp:driver:ok:{request_id} = phone, TTL 900s
   → response: {"verify_id": "..."}

3. POST /auth/driver/login              body: {"verify_id": "..."}
   → 폰번호로 driver 조회 (driver.phone 컬럼 unique)
   → 없으면 → "DRIVER_NOT_REGISTERED" 404 + dispatcher 에게 알림 (옵션)
   → 있으면 → 해당 driver 의 user_id 로 access/refresh token 발급
   → response: {"access_token", "refresh_token", "user": {...}}
```

#### 핵심 결정

| 결정 | 이유 |
| --- | --- |
| 폰번호 자체로 회원가입 X (선등록) | dispatcher 가 driver 마스터 미리 등록 → 폰번호 매칭으로 인증 |
| Phone 컬럼은 `driver.phone` (TeamScoped) 또는 `user.phone` (글로벌) | **`user.phone` 권장** — 한 driver 가 여러 팀 소속 가능. driver 마스터에는 user_id FK 만 |
| OTP 시도 제한 | 5회 (`OTP_MAX_TRIES`) — 같은 ste 값 재사용 |
| SMS gateway | `.env` 의 `SMS_PROVIDER` (`twilio` / `aligo` / `nhn` / `mock`) — `common/sms/factory.py` 패턴 (vessel/ais/factory 와 동일 구조) |
| 회원가입 안 됨 — dispatcher 가 driver 추가 시 | `POST /api/v1/driver` → 백엔드가 user 자동 생성 + driver row + 초대 SMS 발송 |

#### 구현 위치

1. **모델** — `user/model.py` 에 `phone` 컬럼 추가 (글로벌 unique)
2. **Auth service** — `auth/service.py` 에 OTP 메서드 4개:
   - `request_driver_otp(phone) -> request_id`
   - `verify_driver_otp(request_id, code) -> verify_id`
   - `driver_login(verify_id) -> tokens`
3. **Router** — `auth/router.py` 에 3개 엔드포인트
4. **SMS 발송** — `common/sms/` (또는 `auth/sms/`) 신규 모듈
5. **Driver 생성 hook** — `driver/service.py` 의 `create` 가 `user/service.py` 의 `create_or_get_by_phone` 호출

세부 구현 가이드는 driver 작업 시 추가.

### OTP 공통 제한

- 코드 = 6자리 (`secrets.randbelow(1000000)`)
- 시도 제한: `OTP_MAX_TRIES=5` — 초과 시 `OTP_MAX_TRIES` 에러
- 코드 만료 시 `OTP_EXPIRED`, 불일치 시 `OTP_INVALID`
- 성공 후 OTP 키 즉시 삭제, OK 키 생성 (15분 안에 다음 스텝 완료)

### 사용자 enumeration 방지

이메일/폰 시스템에 없어도 request 는 성공한 것처럼 응답. 스팸 대응은 SMS/SMTP 큐 자체에서.

---

## 6. Service / Repository 구조

### AuthService

```python
class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.user_repository = UserRepository(db)
```

- DB 뿐만 아니라 **Redis 도 주입**받음 (세션 / 토큰 / OTP / OAuth state)
- `self.user_repository` 로 UserRepository 직접 사용 (표준 도메인은 `self.repo` 패턴이지만 auth 는 자체 primary repo 가 없음)
- 주요 메서드:
  - `verify_token()`, `create_tokens()`, `rotate_token()`
  - `login_user()`, `logout()`, `issue_new_access_from_request()`, `rotate_refresh_from_request()`
  - `oauth_login()`
  - OTP 관련 (email reset / signup / **driver phone**)
  - **`driver_login(verify_id)` — driver 앱 토큰 발급**

### AuthRepository

Redis 만 사용 (DB 없음). 주로 blacklist / 세션 관련 조작. 현재 헬퍼 수준.

---

## 7. 라우터

`/api/v1/auth/` 하위. 주요 엔드포인트:

- `POST /login` — Basic 인증 (web)
- `POST /logout`
- `POST /token/access`, `/token/refresh`
- `POST /register/email/send`, `/register/email/verify`, `/register`
- `POST /password/reset/request`, `/reset/verify`, `/reset/confirm`
- `GET  /oauth/{provider}`, `/oauth/{provider}/callback`
- **`POST /driver/otp/request`, `/driver/otp/verify`, `/driver/login`** ⭐ TMS 신규 — driver 작업 시 추가

---

## 8. 알려진 상태 / 주의사항

- **`access_token` dependency 만 활성** — JWT 호출자 위주. API Key 통합 인증은 추후 외부 통합 시 활성화 (현재 `api_key` 도메인 자체는 발급/관리만 존재)
- **`permission_guard` 활성 사용** — 대부분 mutation 라우터에 부착. ste 와 다른 점
- **`rate_limit` 미사용** — 외부 API 노출 시 활성화
- **driver phone OTP 미구현** — driver_mobile 작업 시 §5-2 가이드로 구현
- **OAuth state 단회용** — 콜백 도중 네트워크 실패하면 유저가 플로우 다시 시작 (10분 TTL 안)
- **OTP IP 단위 rate limit 없음** — SMS gateway 자체 제한 + `OTP_MAX_TRIES` 로만 방어

---

## 9. 관련 문서

- [`../CLAUDE.md`](../CLAUDE.md) — src 트리
- [`../../CLAUDE.md`](../../CLAUDE.md) — 루트 헌법
- [`../rbac/CLAUDE.md`](../rbac/CLAUDE.md) — `permission_guard` + RolesEnum
- [`../driver_mobile/CLAUDE.md`](../driver_mobile/CLAUDE.md) — 모바일 인증 흐름 (driver phone OTP 사용 예)
