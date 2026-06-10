# src/driver_mobile/CLAUDE.md

⭐ **BFF (Backend for Frontend) 도메인.** Driver 모바일 앱 (`flutter_driver_app`) 전용 라우팅 모음. **자체 model / repository 없음** — 다른 도메인의 service 와 repository 를 호출해 모바일 친화 응답으로 조립.

> **flutter_driver_app 작업 시작 전 이 파일 필독.** 이 도메인의 라우트 / 응답 schema 가 모바일 앱의 API 계약.

---

## 1. 책임

```
Driver Mobile App (Flutter)
  ↓ HTTPS
/api/v1/driver/*   (이 도메인의 라우트)
  ↓ require_driver (role 가드)
  ↓ access_token (JWT 가드)
  ↓ get_team_scope
  ↓
DriverMobileService(db, team_id)
  ├── LegRepository      — driver 의 leg 조회 / 상태 전이
  ├── DriverRepository   — driver 마스터
  ├── LocationPingRepo   — 위치 batch 업로드
  ├── PushTokenRepo      — FCM/APNS 토큰
  ├── ContainerStopRepo  — stop arrive/depart 보고
  └── (필요 시) 다른 도메인 service
```

**핵심 원칙**:
- 자체 model / repository **만들지 마라**. 다른 도메인의 repo / service 호출.
- 모바일 앱이 한 화면을 그리는 데 필요한 데이터를 한 응답에 조립 (REST → BFF).
- WS event 도 driver 가 listen — `leg.driver.assigned` 같은 도메인 event 에 `driver_id` 추가 컨텍스트.

---

## 2. 폴더 구조

```
driver_mobile/
├── __init__.py
├── const/                       # (옵션) 모바일 특화 상수
├── service.py                   # DriverMobileService — 다른 도메인 조립
├── service_v3.py                # 점진 마이그레이션 흔적 — 신규 코드는 service.py
├── router.py                    # /api/v1/driver/* 라우트 모음
└── schemas/
    ├── __init__.py
    ├── request.py               # CheckpointRequest, LocationBatchRequest 등
    └── response.py              # TodayTasksResponse, DriverV3TodayResponse 등
```

**model.py / repository.py 없음** — 의도된 설계.

---

## 3. 인증 흐름

### 3-1. 로그인 (폰번호 + OTP)

```
1. POST /api/v1/auth/driver/otp/request   body: {"phone": "+82..."}
   → SMS 발송, otp:driver:{request_id}
2. POST /api/v1/auth/driver/otp/verify    body: {"request_id", "code"}
   → otp:driver:ok:{request_id} = phone (15분 TTL)
3. POST /api/v1/auth/driver/login         body: {"verify_id"}
   → driver.phone 매칭 → access/refresh 토큰 발급
```

세부 흐름은 `src/auth/CLAUDE.md` §5-2. 백엔드 구현 시 driver 등록 (dispatcher 가 미리 driver 추가 + 폰번호 입력) 이 선행되어야 함.

### 3-2. 토큰 갱신

```
POST /api/v1/auth/token/access   (body 에 refresh JWT)
```

`refresh_token` 가드 (auth/tokens/refresh_token.py).

### 3-3. 라우터 가드 표준 (TMS 패턴 — driver 앱)

```python
@router.<method>(<path>, response_model=...)
async def <handler>(
    <path_params>,
    <body>,
    _1: None = Depends(access_token),              # JWT 검증
    me: UserResponseSchema = Depends(require_driver),  # role == DRIVER
    team_id: int = Depends(get_team_scope),        # X-Team-Id 헤더 → 멤버십
    db: AsyncSession = Depends(get_read_db | get_write_db),
):
    ...
```

`require_driver` 가 RolesEnum.DRIVER 외 거부 — driver 앱이 dispatcher / admin 호출 못 함.

```python
# driver_mobile/router.py (현재 인라인)
def require_driver(me: UserResponseSchema = Depends(get_current_user)) -> UserResponseSchema:
    role = getattr(me, "role", None)
    role_value = getattr(role, "value", role)
    if role_value != RolesEnum.DRIVER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN_ROLE", "message": "DRIVER 만 호출할 수 있습니다."},
        )
    return me
```

> **TODO**: 이 가드는 `user/dependencies/role_guards.py` 로 이동 권장 (다른 도메인도 재사용 가능).

---

## 4. 라우트 카탈로그

`prefix="/api/v1/driver"`, `tags=["driver_mobile"]`.

### 4-1. 오늘 할 일 / 오늘 컨테이너

```python
@router.get("/tasks/today", response_model=TodayTasksResponse)
async def tasks_today(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """오늘 할당된 Leg 목록 (PENDING / IN_TRANSIT)."""
    legs = await DriverMobileService(db, team_id).today_legs(int(me.id))
    return TodayTasksResponse(legs=[LegResponseSchema.model_validate(l) for l in legs])


@router.get("/today", response_model=DriverV3TodayResponse)
async def today_v3(
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    """v3 — 오늘의 컨테이너 + 다음 액션 안내까지 한 응답에 조립."""
    return await get_today_containers_for_driver(db, team_id, driver_user_id=int(me.id))
```

### 4-2. Leg 상태 전이 (Checkpoint)

```python
@router.post("/legs/{leg_id}/checkpoint", response_model=LegResponseSchema)
async def checkpoint(
    leg_id: int,
    body: CheckpointRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """Leg 상태 전이 (PENDING → IN_TRANSIT 등). 본인 leg 검증 + leg.service.transition."""
    return await DriverMobileService(db, team_id).checkpoint_leg(
        leg_id, body.target,
        user_id=int(me.id), failure_reason=body.failure_reason,
    )
```

`CheckpointRequest`:
```python
class CheckpointRequest(RequestSchema):
    target: LegStatus              # IN_TRANSIT / COMPLETED / FAILED
    failure_reason: Optional[str] = None
```

### 4-3. Stop arrive / depart 보고

```python
@router.post("/legs/{leg_id}/stops/{stop_id}/arrive", response_model=...)
async def stop_arrive(leg_id, stop_id, body, ...):
    """stop 도착 보고 — 위도/경도, 도착 시각."""
    return await report_stop_arrive(db, team_id, leg_id, stop_id, body, driver_user_id=int(me.id))


@router.post("/legs/{leg_id}/stops/{stop_id}/depart", response_model=...)
async def stop_depart(leg_id, stop_id, body, ...):
    """stop 출발 보고."""
    return await report_stop_depart(db, team_id, leg_id, stop_id, body, driver_user_id=int(me.id))
```

### 4-4. 위치 batch 업로드

```python
@router.post("/location/batch", response_model=...)
async def location_batch(
    body: LocationBatchRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """오프라인 버퍼링된 위치 데이터 한꺼번에 업로드."""
    return await DriverMobileService(db, team_id).save_location_batch(body, driver_user_id=int(me.id))
```

`LocationBatchRequest`:
```python
class LocationPingItem(RequestSchema):
    latitude: float
    longitude: float
    accuracy_m: Optional[float] = None
    speed_kmh: Optional[float] = None
    heading_deg: Optional[float] = None
    reported_at: datetime

class LocationBatchRequest(RequestSchema):
    pings: List[LocationPingItem]
    leg_id: Optional[int] = None     # 현재 운송 중인 leg 와 연결 (옵션)
```

### 4-5. Push 토큰 등록

```python
@router.post("/push-tokens", response_model=PushTokenResponse)
async def register_push_token(
    body: PushTokenRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """FCM/APNS 토큰 등록 (앱 시작 시 호출)."""
    return await DriverMobileService(db, team_id).register_push_token(body, user_id=int(me.id))
```

`PushTokenRequest`:
```python
class PushTokenRequest(RequestSchema):
    platform: Literal["ios", "android"]
    token: str
    device_id: str                    # 앱 설치 시 발급된 UUID
    app_version: str
```

### 4-6. 사진 / 문서 업로드

```python
@router.post("/legs/{leg_id}/documents", response_model=...)
async def upload_document(
    leg_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
):
    """leg 진행 중 사진 / 서명 / 인수증 업로드."""
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(400, detail={"code": "UNSUPPORTED_FILE_TYPE"})
    # 파일 크기 / MIME 검증 → FileService 위임
    return await DriverMobileService(db, team_id).upload_leg_document(
        leg_id, document_type, file, user_id=int(me.id),
    )


ALLOWED_DOCUMENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf",
}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
```

### 4-7. 첫 비밀번호 변경 (앱 초기 진입)

```python
@router.post("/me/first-password", response_model=...)
async def first_password_change(
    body: FirstPasswordChangeRequest,
    _1: None = Depends(access_token),
    me: UserResponseSchema = Depends(require_driver),
    db: AsyncSession = Depends(get_write_db),
):
    """OTP 로 첫 로그인 후 비밀번호 설정 (옵션 — 일부 운영 정책)."""
    ...
```

---

## 5. Service 패턴 — 다른 도메인 조립

```python
# driver_mobile/service.py
from leg.repository import LegRepository
from leg.service import LegService
from driver.repository import DriverRepository
from location_ping.repository import LocationPingRepository
from push_token.repository import PushTokenRepository


class DriverMobileService:
    def __init__(self, db: AsyncSession, team_id: int):
        self.db = db
        self.team_id = team_id
        self.leg_repo = LegRepository(db, team_id)
        self.driver_repo = DriverRepository(db, team_id)
        self.location_ping_repo = LocationPingRepository(db, team_id)
        self.push_token_repo = PushTokenRepository(db, team_id)

    async def today_legs(self, driver_user_id: int) -> list:
        """오늘 driver 본인에게 할당된 leg."""
        return await self.leg_repo.list_for_driver_today(driver_user_id)

    async def checkpoint_leg(
        self, leg_id: int, target: LegStatus, *, user_id: int, failure_reason: str | None,
    ):
        leg = await self.leg_repo.get(leg_id)
        if not leg: raise NotFoundException("Leg")
        if leg.assigned_driver_user_id != user_id:
            raise AppException(
                code="NOT_OWNED_LEG", message="본인 leg 가 아닙니다.", status_code=403,
            )
        # Leg service 의 transition 위임 (state machine 검증 포함)
        leg_svc = LegService(self.db, self.team_id)
        return await leg_svc.transition(leg_id, target, force=False, reason=failure_reason, actor_user_id=user_id)

    async def save_location_batch(self, body, *, driver_user_id: int):
        # bulk insert
        return await self.location_ping_repo.create_many(
            [{**p.model_dump(), "driver_user_id": driver_user_id, "leg_id": body.leg_id} for p in body.pings],
        )

    async def register_push_token(self, body, *, user_id: int):
        # upsert (device_id unique)
        return await self.push_token_repo.upsert(
            user_id=user_id, device_id=body.device_id,
            platform=body.platform, token=body.token, app_version=body.app_version,
        )

    async def upload_leg_document(self, leg_id, document_type, file, *, user_id):
        # leg 본인 검증 + FileService 위임
        leg = await self.leg_repo.get(leg_id)
        if not leg: raise NotFoundException("Leg")
        if leg.assigned_driver_user_id != user_id:
            raise AppException(code="NOT_OWNED_LEG", status_code=403)
        # FileService 가 presigned URL 또는 직접 업로드 처리
        ...
```

### 핵심 규칙

1. **자체 model / repo 없음** — 모든 데이터 접근은 다른 도메인의 repo 사용
2. **본인 leg 검증** — `leg.assigned_driver_user_id == me.id` 항상 체크
3. **state machine 우회 금지** — `leg_service.transition()` 호출 (driver_mobile 이 직접 status 업데이트 X)
4. **응답은 BFF 친화** — 모바일이 한 화면 그리는 데 필요한 nested 데이터까지 한 응답에

---

## 6. WS event — driver 가 listen 하는 것들

driver 앱이 WebSocket 으로 listen:

| Event | 트리거 | Payload 추가 컨텍스트 |
| --- | --- | --- |
| `leg.driver.assigned` | dispatcher 가 leg 에 driver 할당 | `driver_id`, `leg_id`, `delivery_order_id` |
| `leg.status.changed` | leg 상태 변경 | `previous_status`, `target_status` |
| `notification.created` | driver 에게 알림 발송 | `user_id` (driver), `category` |
| `delivery_order.status.changed` | D/O 상태 변경 (driver 의 leg 가 속한 D/O) | `previous_status`, `target_status` |

driver 앱은 본인 `user_id` / `driver_id` 매칭으로 필터 — 서버는 일괄 publish, 클라이언트가 필터.

### publish 시 추가 컨텍스트 포함

```python
# leg/service.py
await self._emit(
    "leg.driver.assigned",
    result,
    driver_id=body.driver_id,                       # ← 추가
    delivery_order_id=leg.delivery_order_id,        # ← 추가
)
```

---

## 7. 모바일 친화 응답 (BFF Response)

### 단일 화면 = 단일 응답

```python
class DriverV3TodayResponse(ResponseSchema):
    """오늘의 컨테이너 — 한 응답에 leg + container + stop + customer 까지 조립."""
    containers: List[DriverContainerSummary]
    pending_count: int
    in_transit_count: int
    completed_count: int


class DriverContainerSummary(ResponseSchema):
    leg_id: int
    leg_status: LegStatus
    container_id: int
    container_number: str
    size: ContainerSize
    delivery_order_id: int
    delivery_order_status: DeliveryStatus
    customer_name: str
    pickup: Optional[StopSummary] = None
    dropoff: Optional[StopSummary] = None
    next_action: str            # "Pickup at LA Port" / "Dropoff at Warehouse A"


class StopSummary(ResponseSchema):
    stop_id: int
    location_name: str
    address: str
    latitude: float
    longitude: float
    expected_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    departed_at: Optional[datetime] = None
```

웹용 detail 응답 (`DeliveryOrderDetailResponseSchema`) 과 별개 — 모바일은 자기 필요한 형태로 별도.

---

## 8. driver 등록 흐름 (dispatcher 측)

driver 앱 진입 전 사전 등록:

```
1. Dispatcher (web) — POST /api/v1/driver
   body: {"name", "phone", "license_number", ...}
   → 백엔드:
     a. user 자동 생성 (phone unique). role = "DRIVER"
     b. driver row 생성 (user_id FK)
     c. 초대 SMS 발송 (옵션) — "앱 다운로드 + OTP 로그인"

2. Driver (mobile) — 앱 설치 → 폰번호 입력 → OTP 받음 → 로그인
   → access/refresh 발급
   → /driver/push-tokens 등록
   → /driver/today 조회
```

세부: `src/driver/CLAUDE.md` (있다면) 또는 `src/driver/service.py` 의 `create` 메서드 가이드.

---

## 9. 디바이스 식별 / 다중 디바이스

- 한 driver 가 여러 디바이스 사용 가능 (회사 폰 분실 / 개인 폰)
- `push_token.device_id` 별로 토큰 등록
- 로그인 시 새 `did` (`app:{uuid}`) — 기존 세션 무효화 옵션:
  - 정책 A: 한 driver 동시 1 디바이스만 — 새 로그인 시 기존 세션 강제 종료
  - 정책 B: 멀티 디바이스 허용 — 모든 세션 유지

> **결정**: TMS 는 정책 A 권장 — 같은 driver 가 동시 두 디바이스에서 leg 진행 보고 시 충돌 위험.

구현: `auth/service.driver_login` 에서 기존 sids 모두 invalidate.

---

## 10. 알려진 상태

- `service_v3.py` — v2 → v3 점진 마이그레이션 흔적. 신규 코드는 `service.py` 사용. v3 함수 (`get_today_containers_for_driver`, `report_stop_arrive`, `report_stop_depart`) 는 별도 모듈 함수로 일부 노출 중
- `require_driver` 인라인 → `user/dependencies/role_guards.py` 로 이동 권장 (재사용 가능)
- driver phone OTP (`auth/driver/otp/*`) 미구현 — 백엔드 구현 후 mobile 앱 진입
- 사진 업로드 (`/legs/{id}/documents`) — FileService 와 연동 필요 (presigned URL 권장)
- WS event 의 driver 필터링 (`driver_id` 매칭) — 일괄 broadcast + 클라이언트 필터 방식

---

## 11. PR 리뷰 체크리스트

- [ ] 자체 model / repository 추가 X (다른 도메인 호출만)
- [ ] 모든 라우터에 `_1: None = Depends(access_token)` + `me: UserResponseSchema = Depends(require_driver)`
- [ ] team_id 받기 (`Depends(get_team_scope)`)
- [ ] 본인 leg / driver 검증 (`leg.assigned_driver_user_id == me.id`)
- [ ] state machine 우회 X (`leg_service.transition` 호출)
- [ ] WS event 발행은 도메인 service 에서 (driver_mobile 자체는 redis 미주입)
- [ ] 응답 schema 는 모바일 친화 (단일 화면 = 단일 응답, nested 조립)
- [ ] 사진 업로드는 FileService 위임 + MIME / size 검증
- [ ] push token 은 device_id unique upsert

---

## 12. flutter_driver_app 작업 시 매핑

flutter_driver_app 의 도메인 → 이 백엔드 라우트:

| Flutter 도메인 | API |
| --- | --- |
| `auth` | `POST /auth/driver/otp/request|verify|login` |
| `today` (홈 화면) | `GET /driver/today` 또는 `/driver/tasks/today` |
| `leg` (운송 진행) | `POST /driver/legs/{id}/checkpoint` |
| `stop` (정차) | `POST /driver/legs/{id}/stops/{stop_id}/arrive|depart` |
| `location` (백그라운드 추적) | `POST /driver/location/batch` |
| `push` (앱 시작 시) | `POST /driver/push-tokens` |
| `document` (사진 업로드) | `POST /driver/legs/{id}/documents` |
| `notification` (WS listen) | WebSocket `wss://.../ws?...` |

세부 응답 형태는 이 도메인의 `schemas/response.py` 가 단일 진실.

---

## 13. 관련 문서

- [`../CLAUDE.md`](../CLAUDE.md) — src 트리
- [`../auth/CLAUDE.md`](../auth/CLAUDE.md) — `access_token` + driver phone OTP (§5-2)
- [`../rbac/CLAUDE.md`](../rbac/CLAUDE.md) — `RolesEnum`, `require_driver`
- [`../delivery_order/CLAUDE.md`](../delivery_order/CLAUDE.md) — D/O 흐름 (driver 가 leg 통해 영향)
- (향후) `../leg/CLAUDE.md` — leg state machine
- (향후) `../location_ping/CLAUDE.md` — 위치 배치 적재
- (향후) `../push_token/CLAUDE.md` — FCM/APNS 발송
- `flutter_driver_app/CLAUDE.md` (만들 예정) — Flutter 클라이언트 가이드. 이 API 와 짝
