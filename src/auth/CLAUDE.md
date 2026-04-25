# src/auth/CLAUDE.md

인증/세션/OAuth/OTP를 담당. **모든 보호 엔드포인트의 단일 게이트는 `jwt_or_api_key` 의존성이다.**

---

## 1. `jwt_or_api_key` — canonical auth dependency

**모든 보호 엔드포인트에서 반드시 이것을 사용한다.** JWT와 API Key를 하나의 `AuthResult` 추상으로 통합한다.

### 시그니처

```python
# auth/dependencies/jwt_or_api_key.py
async def jwt_or_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthResult:
    ...
```

### AuthResult 구조

```python
@dataclass
class AuthResult:
    auth_type: str              # "jwt" | "api_key"
    user_id: Optional[int]      # API Key 호출자는 None
    team_id: Optional[int]      # JWT 호출자는 X-Team-Id 헤더 있을 때만 값 있음
    plan: str = "free"          # API Key 호출자는 키 row에서 resolve
```

### 분기 로직

1. **API Key 경로** — `X-API-Key` 헤더가 있으면
   - `ApiKeyRepository.get_active_by_key()` 조회
   - 없으면 `UnauthorizedException`
   - 있으면 `AuthResult(auth_type="api_key", user_id=None, team_id=..., plan=...)`
   - best-effort로 `touch_last_used()` (비동기 태스크처럼 실패 무시)

2. **JWT 경로** — `Authorization: Bearer ...` 헤더가 있으면
   - `bearer_token` dependency에 위임 (상세한 세션 검증 수행)
   - `X-Team-Id` 헤더가 있으면 해당 팀 멤버인지 확인 → 아니면 `NOT_TEAM_MEMBER` 403
   - `AuthResult(auth_type="jwt", user_id=..., team_id=<헤더값 또는 None>, plan=...)`

3. **둘 다 없으면** → `UnauthorizedException`

### 라우터 사용

```python
@router.post("/{team_id}", response_model=TeamResponseSchema)
async def update_team(
    team_id: int,
    body: UpdateTeamRequestSchema,
    auth: AuthResult = Depends(jwt_or_api_key),         # ← 이 위치
    _rl: None = Depends(rate_limit),
    me: UserResponseSchema = Depends(get_current_user),
    db: AsyncSession = Depends(get_write_db),
):
    ...
```

**Depends 순서는 엄격히 지킨다**: path params → body → `jwt_or_api_key` → `rate_limit` → `get_current_user` → `get_read_db`/`get_write_db`. (세부: `src/team/CLAUDE.md`)

### 팀 스코프 강제

`AuthResult.team_id`가 None일 수 있다 (JWT 호출자가 아직 팀 미선택). 팀 범위가 필수인 엔드포인트는 **라우터 또는 서비스에서 직접 가드**:

**팀 scoped 엔드포인트는 `Depends(get_team_scope)` 를 추가 주입**하여 `auth.team_id` 가 None 이면 400 으로 실패시킨다. 인라인 헬퍼 (`_require_team(auth)`) 는 과거 패턴이며 새 코드에서는 `get_team_scope` 를 사용한다:

```python
from team.dependencies.get_team_scope import get_team_scope

@router.post("", response_model=...)
async def handler(
    body: ...,
    auth: AuthResult = Depends(jwt_or_api_key),
    _rl: None = Depends(rate_limit),
    team_id: int = Depends(get_team_scope),      # ← 자동 400 TEAM_REQUIRED
    db: AsyncSession = Depends(get_write_db),
):
    svc = SomeService(db, team_id)
    ...
```

RBAC 기반 권한 체크는 `src/rbac/CLAUDE.md` 참조. 팀 scoped 라우터 규약 세부는 `src/team/CLAUDE.md`.

### `get_team_scope` 구현

```python
# team/dependencies/get_team_scope.py
async def get_team_scope(
    auth: AuthResult = Depends(jwt_or_api_key),
) -> int:
    if auth.team_id is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "TEAM_REQUIRED", "message": "..."},
        )
    return auth.team_id
```

- `jwt_or_api_key` 가 이미 API Key 경로와 JWT 경로 모두에서 `auth.team_id` 를 결정해둔다 (JWT 는 X-Team-Id 헤더 + 멤버십 검증, API Key 는 키 row)
- `get_team_scope` 는 얇은 래퍼 — 내부 Redis 재검증 없음 (이미 `jwt_or_api_key` 에서 검증됨)
- FastAPI 가 `Depends(jwt_or_api_key)` 를 캐싱하므로 중복 호출 부하 없음

---

## 2. 부속 의존성

### `bearer_token` (`auth/dependencies/bearer_token.py`)

`jwt_or_api_key`의 JWT 경로에서 호출된다. 직접 쓸 일은 거의 없지만 "JWT만 허용" 엔드포인트가 필요하면 여기.

**수행하는 검증**:
1. JWT 디코드 (`AuthService.verify_token()`)
2. 토큰 claims 필수 필드 확인 (`type`, `sid`, `jti`, `sub`)
3. Web 요청(`did`가 `web:`로 시작)이면 브라우저 cookie `did` 일치 확인
4. Redis blacklist 확인 (`bl:a:{jti}`)
5. Redis session 존재 확인 (`sess:{sid}`)
6. 세션 데이터 (`uid`, `did`) 토큰과 일치 확인
7. 디바이스 → 세션 매핑 확인 (`device:{did}:sid`)
8. 사용자 로드 (`user:{uid}` 캐시 → DB fallback)

**결과**: `request.state.user/token/token_type/payload`에 채운다 (리턴값 없음).

### `basic_token` (`auth/dependencies/basic_token.py`)

HTTP Basic (email + 평문 비밀번호). **로그인 엔드포인트에서만 사용** (`POST /api/v1/auth/login`). 다른 용도 금지.

### `access_token` (`auth/dependencies/access_token.py`)

`bearer_token`을 감싸서 `token_type == "access"`만 허용. 현재 미사용. 리프레시 토큰이 아닌 access 토큰만 받아야 하는 엔드포인트를 만들 때 활성화.

### `rate_limit` (`auth/dependencies/rate_limit.py`)

**모든 보호 엔드포인트에 필수**로 `_rl: None = Depends(rate_limit)` 추가.

```python
PLAN_LIMITS = {"free": 100, "basic": 1000, "pro": 10000}   # 일일 호출
RATE_LIMIT_TTL = 30 * 86400                                  # Redis 키 30일 TTL (usage dashboard용)
```

**동작**:
- JWT 호출자 → 스킵 (웹 UI는 클라이언트 스로틀링 가정)
- `auth.team_id` None → 스킵
- API Key 호출자 → `rate_limit:{team_id}:{YYYY-MM-DD}` Redis 카운터 증가
- 초과 시 `AppException(code="RATE_LIMIT_EXCEEDED", status=429)`
- 응답 헤더 자동 추가: `X-RateLimit-Limit/Remaining/Reset`

**다른 티어가 필요한 엔드포인트**가 생기면 `rate_limit`을 그대로 쓰지 말고 별도 dependency (`rate_limit_premium` 등)로 만든다.

### `get_current_user` (`user/dependencies/current_user.py`)

`request.state.user`에서 현재 사용자를 뽑아 `UserResponseSchema`로 반환. **`jwt_or_api_key` 이후**에 주입되어야 정상 동작한다 (Depends 순서가 중요한 이유).

API Key 호출자처럼 user가 없는 경우엔 사용하면 401 발생. "사용자가 꼭 필요한" 엔드포인트에서만 주입한다.

---

## 3. JWT + Session 구조

### Token TTL

| 종류 | TTL | 설정 |
| --- | --- | --- |
| Access token | 30분 | `ACCESS_TTL=1800` |
| Refresh token | ~2.2시간 | `REFRESH_TTL=8000` |

### Redis 키 레이아웃

로그인 시 `AuthService._create_session()`이 다음 키들을 모두 세팅 (TTL = `REFRESH_TTL`):

| 키 | 값 | 용도 |
| --- | --- | --- |
| `sess:{sid}` | `{"uid": int, "did": str}` JSON | 세션 메타데이터 |
| `refresh:{sid}` | 현재 refresh JWT 문자열 | rotation 검증 |
| `device:{did}:sid` | `sid` | 디바이스 → 세션 역인덱스 |
| `u:{uid}:sids` | Set of sid | 유저의 모든 세션 (로그아웃 올 기능용) |
| `bl:a:{jti}` | "1" | Access 토큰 블랙리스트 (선택적) |

### 디바이스 식별 (`did`)

- Web: `"web:{browser_id}"` where `browser_id`는 httpOnly cookie에 UUID로 저장
- App: 앱이 직접 제공한 디바이스 식별자

쿠키가 사라지거나 브라우저가 다르면 `did`가 바뀌어 기존 토큰이 무효화된다 (의도된 보안 동작 — `ACCOUNT_SWITCHED` 반환).

### 토큰 로테이션 (`AuthService.rotate_token`)

1. Refresh JWT 디코드 + 검증
2. `refresh:{sid}`와 제출된 값 일치 확인 (불일치 = 재사용 감지)
3. 새 access 토큰 발급
4. `is_refresh=True`면 refresh 토큰도 새로 발급하고 Redis 4개 키 전부 TTL 갱신

### 엔드포인트

| Method | Path | 용도 | Dependency |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | 로그인 (email + 비밀번호) | `basic_token` |
| POST | `/api/v1/auth/token/access` | refresh → 새 access | 쿠키 또는 Bearer의 refresh |
| POST | `/api/v1/auth/token/refresh` | refresh 로테이션 | Bearer의 refresh |
| POST | `/api/v1/auth/logout` | refresh cookie 제거 | 없음 |

Web은 refresh를 httpOnly cookie로, App은 body로 내려준다. `settings.cookie_secure`가 prod에서 True.

---

## 4. OAuth

### 구조

`auth/oauth/base.py`의 추상 클래스 `OAuthProviderBase`를 각 provider가 상속.

```
auth/oauth/
├── base.py         # OAuthProviderBase, OAuthUserInfo
├── google.py       # GoogleOAuthProvider
├── kakao.py        # 추후 추가 시
└── apple.py        # 추후 추가 시
```

### 새 provider 추가 방법

1. `auth/oauth/{provider}.py`에 `{Provider}OAuthProvider(OAuthProviderBase)` 작성
2. 8개 프로퍼티 구현: `provider`, `authorization_url`, `token_url`, `userinfo_url`, `client_id`, `client_secret`, `redirect_uri`, `scopes`
3. 2개 메서드 구현:
   - `async exchange_code_for_token(code) -> dict` (httpx로 token endpoint 호출)
   - `async get_user_info(token_response) -> OAuthUserInfo`
4. `auth/router.py`의 `_get_oauth_provider()`에 분기 추가
5. `.env`에 `{PROVIDER}_CLIENT_ID/SECRET/REDIRECT_URI` 추가 → `common/const/settings.py`에 필드 추가

### OAuthUserInfo

```python
@dataclass
class OAuthUserInfo:
    provider: AuthProviderEnum
    oauth_id: str           # provider별 고유 id (Google의 sub 등)
    email: Optional[str] = None
    name: Optional[str] = None
    profile_image: Optional[str] = None
```

### 공통 흐름 (base 클래스 제공)

- `generate_state()` → Redis `oauth_state:{provider}:{state}` 저장 (TTL=`OAUTH_STATE_TTL=600`)
- `verify_state()` → 검증 후 **즉시 삭제** (단회용, 콜백 재시도 불가)
- `get_authorization_url()` → state 포함한 authorize URL 빌드
- `authenticate(code, state)` → verify_state → exchange_code → get_user_info (orchestration)

### 라우터 흐름

```
GET  /api/v1/auth/oauth/{provider}          → 302 → provider authorize URL
GET  /api/v1/auth/oauth/{provider}/callback → exchange code → oauth_login → 302 → frontend
```

Callback 라우터는 **예외 발생 시 frontend의 `/login?error=oauth_failed`로 redirect** — OAuth는 redirect flow라 JSON 에러를 반환할 수 없음. 유일하게 라우터 레벨에서 `try/except Exception`을 감싸는 케이스.

### `AuthService.oauth_login()`

- 기존 이메일이 다른 provider로 가입돼 있으면 `USE_OAUTH_LOGIN` 또는 `USE_PASSWORD_LOGIN` 에러
- 없으면 user 생성, 있으면 로그인 — 자동 provisioning

---

## 5. OTP (Password Reset + Signup)

두 플로우가 동일한 패턴 (키 prefix만 다름).

### Password Reset

| Step | Endpoint | Redis 키 | TTL |
| --- | --- | --- | --- |
| 1. 코드 요청 | `POST /api/v1/auth/password/reset/request` | `otp:reset:{request_id}` = `{"email", "code", "tries": 0}` | 180초 |
| 2. 코드 검증 | `POST /api/v1/auth/password/reset/verify` | `otp:ok:{request_id}` = email | 900초 |
| 3. 비밀번호 변경 | `POST /api/v1/auth/password/reset/confirm` | — | — |

### Signup

| Step | 키 prefix | 비고 |
| --- | --- | --- |
| 코드 요청 | `otp:signup:` | password reset과 동일 구조 |
| 코드 검증 | `otp:signup_ok:` | |
| 계정 생성 | — | `register_and_login_user()` — 생성 후 자동 로그인 |

### 제한

- 코드 = 6자리 (`secrets.randbelow(1000000)`)
- 시도 제한: `OTP_MAX_TRIES=5` — 초과 시 `OTP_MAX_TRIES` 에러
- 코드 만료 시 `OTP_EXPIRED`, 불일치 시 `OTP_INVALID`
- 성공 후 OTP 키 즉시 삭제, OK 키 생성 (15분 안에 confirm 스텝 완료해야 함)

### 이메일 전송

`common/email/smtp_sender.py`의 `send_email_html()`. SMTP 미설정 시 콘솔 출력.

### 사용자 enumeration 방지

시스템에 없는 이메일에 대해서도 request는 성공한 것처럼 응답한다 (실제 코드 패턴). 스팸 대응은 SMTP 큐에서.

---

## 6. Repository/Service 구조

### AuthService

```python
class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.user_repository = UserRepository(db)
```

- DB 뿐만 아니라 **Redis도 주입**받음 (세션/토큰/OTP/OAuth state)
- `self.user_repository`로 UserRepository 직접 사용 (표준 도메인은 `self.repo` 패턴이지만 auth는 자체 primary repo가 없음)
- 주요 메서드:
  - `verify_token()`, `create_tokens()`, `rotate_token()`
  - `login_user()`, `logout()`, `issue_new_access_from_request()`, `rotate_refresh_from_request()`
  - `oauth_login()`
  - OTP 관련 4쌍 (request/verify + reset/signup)

### AuthRepository

Redis만 사용 (DB 없음). 주로 blacklist/세션 관련 조작용. 현재는 헬퍼 수준.

---

## 7. 라우터

`/api/v1/auth/` 하위. 주요 엔드포인트:

- `POST /login` — Basic 인증
- `POST /logout`
- `POST /token/access`, `/token/refresh`
- `POST /register/email/send`, `/register/email/verify`, `/register`
- `POST /password/reset/request`, `/reset/verify`, `/reset/confirm`
- `GET  /oauth/{provider}`, `/oauth/{provider}/callback`

**로그인/OAuth start/OAuth callback을 제외하면 전부 `jwt_or_api_key` 적용됨**. 로그인 엔드포인트는 예외적으로 `basic_token`만 사용.

---

## 주의사항 / 알려진 상태

- **JWT 호출자에는 rate_limit이 적용되지 않는다** — 웹 UI가 오남용하지 않는다는 가정. 필요하면 JWT에도 팀 단위 쿼터를 붙이는 variant 추가.
- **`access_token` dependency는 정의만 있고 미사용** — access-only 엔드포인트가 생기면 활성화.
- **OAuth state는 단회용** — 콜백 도중 네트워크 실패하면 유저가 플로우를 다시 시작해야 함 (10분 TTL 안에).
- **OTP는 IP 단위 rate limit 없음** — 같은 이메일로 여러 요청 가능. 남용 대응은 SMTP 큐에 의존.
- 디바이스 전환/쿠키 삭제 시 기존 토큰은 `ACCOUNT_SWITCHED`로 거부됨 — 의도된 보안 동작.
