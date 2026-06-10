# src/delivery_order/CLAUDE.md

⭐ **TMS 대표 도메인.** 헤더 (`delivery_order`) + 라인 (`container`) 분리 + 상태 머신 (`state_machine.py`). 새 도메인이 비슷한 패턴 (헤더 + 라인 + 상태 전이) 이라면 이 폴더를 그대로 복사 후 도메인 명만 바꾸면 된다.

> **선행**: `src/team/CLAUDE.md` (표준 도메인 규약) + `src/common/CLAUDE.md` (TeamScopedMixin 등).

---

## 0. 도메인 책임

```
DeliveryOrder (D/O)
├── 헤더 — BL number / Booking / customer / terminal / vessel / ETA / 상태
├── Container (1:N) — 컨테이너 번호, 사이즈, 라인 단위 일정
├── Leg (1:N via container) — 트럭 한 대의 운송 구간
├── Settlement (1:N via leg) — 운임 정산
└── State Machine — PLANNING → DISPATCHED → YARD_STAGED → FINAL_DELIVERY → EMPTY_STAGED → COMPLETED
```

상태 전이 시 게이트 검증 (legs 상태 / container 완료 여부) 필요.

---

## 1. 폴더 구조

```
delivery_order/
├── __init__.py
├── const/
│   ├── status.py            # DeliveryStatus, ShipmentDirection
│   └── ...
├── model.py                 # DeliveryOrderModel — 헤더만
├── repository.py            # DeliveryOrderRepository
├── service.py               # DeliveryOrderService — CRUD + transition
├── state_machine.py         # TransitionContext, _ALLOWED, assert_can_transition
├── router.py
└── schemas/
    ├── __init__.py
    ├── request.py
    └── response.py
```

라인 도메인 `container/` 는 별도 폴더 (1:N 가 컨테이너 / 라인이 너무 크게 자라서 분리됨). leg / leg_stop / leg_layer 도 모두 별도 폴더.

---

## 2. Model — 헤더만 (라인은 별도 폴더)

```python
# delivery_order/model.py
from common.model.base_model import Base
from common.model.team_scoped_mixin import TeamScopedMixin
from delivery_order.const.status import DeliveryStatus, ShipmentDirection

class DeliveryOrderModel(Base, TeamScopedMixin):
    __tablename__ = "delivery_order"

    # 상태 / 방향
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, name="delivery_status"),
        default=DeliveryStatus.PLANNING,
        server_default=DeliveryStatus.PLANNING.value,
        nullable=False,
    )
    direction: Mapped[ShipmentDirection] = mapped_column(
        SAEnum(ShipmentDirection, name="shipment_direction"),
        nullable=False,
    )

    # 식별 / 참조
    bl_number:      Mapped[str | None] = mapped_column(String(64), nullable=True)
    booking_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference:      Mapped[str | None] = mapped_column(String(120), nullable=True)

    # FK — 도메인 간이라 단순 FK + ondelete 분기
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False,
    )
    terminal_id: Mapped[int | None] = mapped_column(
        ForeignKey("terminal.id", ondelete="SET NULL"), nullable=True,
    )
    vessel_id: Mapped[int | None] = mapped_column(
        ForeignKey("vessel.id", ondelete="SET NULL"), nullable=True,
    )

    # 헤더 단위 일정 (라인 단위는 ContainerModel)
    eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 게이트
    bl_released: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)

    # 메모
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("team_id", "id",                 name="uq_delivery_order_team_id_id"),
        Index("ix_do_team_status",                         "team_id", "status"),
        Index("ix_do_team_direction",                      "team_id", "direction"),
        Index("ix_do_team_customer",                       "team_id", "customer_id"),
        Index("ix_do_team_active_id",                      "team_id", "is_active", "id"),
        Index("ix_do_team_updated_at",                     "team_id", "updated_at"),
    )
```

### 라인 (container) 의 복합 FK

```python
# container/model.py
class ContainerModel(Base, TeamScopedMixin):
    __tablename__ = "container"
    __with_team_rel__ = False                    # 라인은 .team 관계 제거

    delivery_order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    container_number: Mapped[str] = mapped_column(String(20), nullable=False)
    size: Mapped[ContainerSize] = mapped_column(SAEnum(ContainerSize, name="container_size"), nullable=False)
    # ...

    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "delivery_order_id"],
            ["delivery_order.team_id", "delivery_order.id"],
            ondelete="CASCADE",
            name="fk_container_do_team_id_id",
        ),
        UniqueConstraint("team_id", "id", name="uq_container_team_id_id"),
        UniqueConstraint("team_id", "container_number", name="uq_container_team_number"),
        Index("ix_container_team_id_id", "team_id", "id"),
        Index("ix_container_team_do", "team_id", "delivery_order_id"),
    )
```

---

## 3. State Machine — 별도 파일

```python
# delivery_order/state_machine.py
from dataclasses import dataclass
from common.exceptions.base import AppException
from delivery_order.const.status import DeliveryStatus
from delivery_order.model import DeliveryOrderModel
from leg.model import LegModel


class InvalidStateTransitionError(AppException):
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(
            code="ERR_INVALID_STATE_TRANSITION",
            message=message,
            status_code=422,
            detail=details,
        )


@dataclass
class TransitionContext:
    """게이트 검증을 위한 컨텍스트 — service 가 사전 로드."""
    do: DeliveryOrderModel
    legs: list[LegModel]


_ALLOWED: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.PLANNING:       {DeliveryStatus.DISPATCHED},
    DeliveryStatus.DISPATCHED:     {DeliveryStatus.YARD_STAGED, DeliveryStatus.FINAL_DELIVERY, DeliveryStatus.PLANNING},
    DeliveryStatus.YARD_STAGED:    {DeliveryStatus.FINAL_DELIVERY, DeliveryStatus.DISPATCHED},
    DeliveryStatus.FINAL_DELIVERY: {DeliveryStatus.EMPTY_STAGED, DeliveryStatus.COMPLETED, DeliveryStatus.YARD_STAGED},
    DeliveryStatus.EMPTY_STAGED:   {DeliveryStatus.COMPLETED, DeliveryStatus.FINAL_DELIVERY},
    DeliveryStatus.COMPLETED:      {DeliveryStatus.EMPTY_STAGED},  # 사후 보정 허용
}


def assert_can_transition(ctx: TransitionContext, target: DeliveryStatus, *, force: bool = False) -> None:
    """게이트 검증. force=True 면 그래프 검증도 생략 (관리자 점프)."""
    if force:
        return

    src = ctx.do.status
    allowed = _ALLOWED.get(src, set())
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition {src.value} → {target.value}",
            details={
                "from": src.value, "to": target.value,
                "allowed": [s.value for s in allowed],
            },
        )

    # 추가 게이트 — 비즈니스 의미별 검증
    if target == DeliveryStatus.DISPATCHED:
        if not ctx.legs:
            raise InvalidStateTransitionError(
                "leg 가 하나 이상 있어야 디스패치 가능.",
                details={"reason": "NO_LEGS"},
            )
    # ... 다른 게이트
```

### 왜 별도 파일

- 상태 전이 규칙은 **비즈니스 핵심** — 한 곳에 응집 (`_ALLOWED` dict)
- 추가 게이트 (legs 검증, container 완료 여부) 가 늘어나면 service 가 비대해짐
- 테스트 작성 용이 (state machine 만 단위 테스트)
- 다른 도메인 (`leg/state_machine.py`, `settlement/state_machine.py`) 도 같은 패턴

---

## 4. Service — CRUD + transition

```python
class DeliveryOrderService:
    def __init__(self, db: AsyncSession, team_id: int, redis: Optional[Redis] = None):
        self.db = db
        self.team_id = team_id
        self.redis = redis
        self.repo = DeliveryOrderRepository(db, team_id)
        self.container_repo = ContainerRepository(db, team_id)
        self.leg_repo = LegRepository(db, team_id)

    # ─── CRUD ───────────────────────────────────────

    async def create(self, body: DeliveryOrderCreateRequest, *, actor_user_id: int) -> DeliveryOrderDetailResponseSchema:
        do = await self.repo.create(
            body.model_dump(exclude_unset=True, exclude={"containers"}),
            actor_user_id=actor_user_id,
        )
        if body.containers:
            await self.container_repo.create_many(
                [{**c.model_dump(), "delivery_order_id": do.id} for c in body.containers],
                actor_user_id=actor_user_id,
            )
            await self.db.refresh(do)

        result = DeliveryOrderDetailResponseSchema.model_validate(do)
        await self._emit("delivery_order.created", result)
        return result

    async def get_detail(self, do_id: int) -> DeliveryOrderDetailResponseSchema:
        do = await self.repo.get_with_relations(do_id)
        if not do: raise NotFoundException("DeliveryOrder")
        return DeliveryOrderDetailResponseSchema.model_validate(do)

    async def list_paginated(self, request: PaginateDeliveryOrderRequest):
        result = await self.repo.list_paginated(request)
        result.data = [DeliveryOrderResponseSchema.model_validate(do) for do in result.data]
        return result

    async def update(self, do_id: int, body: DeliveryOrderUpdateRequest, *, actor_user_id: int):
        obj = await self.repo.get(do_id)
        if not obj: raise NotFoundException("DeliveryOrder")
        # 디스패치 된 D/O 의 일부 필드 변경 차단
        if obj.status != DeliveryStatus.PLANNING:
            if "customer_id" in body.model_dump(exclude_unset=True):
                raise AppException(
                    code="DO_LOCKED_FIELD",
                    message="디스패치 된 D/O 의 customer 변경 불가.",
                    status_code=409,
                )
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        obj.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(obj)
        result = DeliveryOrderResponseSchema.model_validate(obj)
        await self._emit("delivery_order.updated", result)
        return result

    async def delete(self, do_id: int, *, actor_user_id: int):
        obj = await self.repo.get(do_id)
        if not obj: raise NotFoundException("DeliveryOrder")
        if obj.status != DeliveryStatus.PLANNING:
            raise AppException(
                code="DO_LOCKED",
                message="진행 중 D/O 는 삭제 불가. 먼저 PLANNING 으로 되돌리세요.",
                status_code=409,
            )
        obj.is_active = False
        obj.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(obj)
        result = DeliveryOrderResponseSchema.model_validate(obj)
        await self._emit("delivery_order.deleted", result)
        return result

    # ─── State Transition ────────────────────────────

    async def transition(self, do_id: int, target: DeliveryStatus, *, force: bool = False, reason: str | None = None, actor_user_id: int):
        do = await self.repo.get_with_relations(do_id)
        if not do: raise NotFoundException("DeliveryOrder")

        legs = await self.leg_repo.list_by_delivery_order(do_id)
        ctx = TransitionContext(do=do, legs=legs)

        assert_can_transition(ctx, target, force=force)

        prev = do.status
        do.status = target
        do.updated_by_user_id = actor_user_id
        await self.db.flush()
        await self.db.refresh(do)

        result = DeliveryOrderResponseSchema.model_validate(do)
        await self._emit("delivery_order.status.changed", result, previous_status=prev.value, target_status=target.value, reason=reason)
        return result

    # 편의 메서드 — 자주 쓰는 전이는 명시적 이름
    async def dispatch(self, do_id: int, *, actor_user_id: int):
        return await self.transition(do_id, DeliveryStatus.DISPATCHED, actor_user_id=actor_user_id)

    async def complete(self, do_id: int, *, actor_user_id: int):
        return await self.transition(do_id, DeliveryStatus.COMPLETED, actor_user_id=actor_user_id)

    # ─── Sync ────────────────────────────────────────

    async def sync_delta(self, since):
        return await self.repo.sync_delta(since)

    # ─── Helper ──────────────────────────────────────

    async def _emit(self, event_type: str, entity, **extra):
        if self.redis:
            await publish_entity_event(self.redis, self.team_id, event_type, entity, **extra)
```

### 핵심 패턴

1. **헤더만 service 가 다룸** — 컨테이너 / leg 는 `container_repo` / `leg_repo` 직접 사용
2. **transition** 은 `state_machine.py` 의 `assert_can_transition` 통과 후 status 업데이트
3. **WS event** — `transition` 은 `<domain>.status.changed` (단순 update 와 별도) — `previous_status`, `target_status`, `reason` 추가 컨텍스트
4. **편의 메서드** — `dispatch` / `complete` 같이 자주 쓰는 전이는 명시적 이름. router 에서 단순 호출

---

## 5. Router — transition / bulk 포함

```python
router = APIRouter(prefix="/api/v1/delivery-orders", tags=["delivery-orders"])

# ─── 단건 CRUD ───────────────────────────────────────

@router.post("", response_model=DeliveryOrderDetailResponseSchema)
async def create_delivery_order(
    body: DeliveryOrderCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DeliveryOrderService(db, team_id, redis=redis).create(
        body, actor_user_id=int(me.id),
    )


@router.get("", response_model=CursorPaginationResult[DeliveryOrderResponseSchema])
async def list_delivery_orders(
    request: PaginateDeliveryOrderRequest = Depends(),
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DeliveryOrderService(db, team_id).list_paginated(request)


# ─── Sync (path param 보다 먼저!) ─────────────────────

@router.get("/sync", response_model=SyncResponse)
async def sync_delivery_orders(
    since: str,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DeliveryOrderService(db, team_id).sync_delta(since)


# ─── 단건 (path param) ───────────────────────────────

@router.get("/{do_id}", response_model=DeliveryOrderDetailResponseSchema)
async def get_delivery_order(
    do_id: int,
    _1: None = Depends(access_token),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_read_db),
):
    return await DeliveryOrderService(db, team_id).get_detail(do_id)


@router.patch("/{do_id}", response_model=DeliveryOrderResponseSchema)
async def update_delivery_order(
    do_id: int,
    body: DeliveryOrderUpdateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DeliveryOrderService(db, team_id, redis=redis).update(
        do_id, body, actor_user_id=int(me.id),
    )


@router.delete("/{do_id}", response_model=DeliveryOrderDeleteResponseSchema)
async def delete_delivery_order(
    do_id: int,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DeliveryOrderService(db, team_id, redis=redis).delete(
        do_id, actor_user_id=int(me.id),
    )


# ─── Transition ──────────────────────────────────────

@router.post("/{do_id}/transition", response_model=DeliveryOrderResponseSchema)
async def transition_delivery_order(
    do_id: int,
    body: DeliveryOrderTransitionRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_DISPATCH)),  # 또는 별도 가드 (DO_TRANSITION)
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DeliveryOrderService(db, team_id, redis=redis).transition(
        do_id, body.target, force=body.force, reason=body.reason,
        actor_user_id=int(me.id),
    )


# 자주 쓰는 편의 라우트 (옵션 — 또는 transition 으로 통일)
@router.post("/{do_id}/dispatch", response_model=DeliveryOrderResponseSchema)
async def dispatch_delivery_order(
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


# ─── Bulk ────────────────────────────────────────────

@router.post("/bulk", response_model=DeliveryOrderBulkCreateResponseSchema)
async def bulk_create_delivery_orders(
    body: DeliveryOrderBulkCreateRequest,
    _1: None = Depends(access_token),
    _2: None = Depends(permission_guard(DO_WRITE)),
    team_id: int = Depends(get_team_scope),
    db: AsyncSession = Depends(get_write_db),
    redis: Redis = Depends(get_write_redis),
    me: UserResponseSchema = Depends(get_current_user),
):
    return await DeliveryOrderService(db, team_id, redis=redis).bulk_create(
        body, actor_user_id=int(me.id),
    )
```

---

## 6. Schemas

```python
# delivery_order/schemas/request.py

class DeliveryOrderCreateRequest(RequestSchema):
    direction: ShipmentDirection
    customer_id: int
    terminal_id: Optional[int] = None
    vessel_id: Optional[int] = None
    bl_number: Optional[str] = Field(None, max_length=64)
    booking_number: Optional[str] = Field(None, max_length=64)
    reference: Optional[str] = Field(None, max_length=120)
    eta: Optional[datetime] = None
    internal_note: Optional[str] = None
    containers: List[ContainerCreateRequest] = []   # 헤더 생성 시 라인 함께 작성 가능


class DeliveryOrderUpdateRequest(RequestSchema):
    # 모두 Optional — PATCH 시맨틱
    customer_id: Optional[int] = None
    terminal_id: Optional[int] = None
    vessel_id: Optional[int] = None
    bl_number: Optional[str] = Field(None, max_length=64)
    booking_number: Optional[str] = Field(None, max_length=64)
    eta: Optional[datetime] = None
    bl_released: Optional[bool] = None
    internal_note: Optional[str] = None


class DeliveryOrderTransitionRequest(RequestSchema):
    target: DeliveryStatus
    force: bool = False                # admin 권한 점프
    reason: Optional[str] = None


class PaginateDeliveryOrderRequest(BasePaginationSchema):
    order__created_at: Optional[Literal["ASC", "DESC"]] = "DESC"
    order__eta: Optional[Literal["ASC", "DESC"]] = None
    where__status__equal: Optional[DeliveryStatus] = None
    where__direction__equal: Optional[ShipmentDirection] = None
    where__customer_id__equal: Optional[int] = None
    where__bl_number__i_like: Optional[str] = None
    include_inactive: bool = Field(default=False)


class DeliveryOrderBulkCreateRequest(RequestSchema):
    items: List[DeliveryOrderCreateRequest]


# ─── Response ────────────────────────────────────────

class DeliveryOrderResponseSchema(ResponseSchema):
    id: int
    status: DeliveryStatus
    direction: ShipmentDirection
    customer_id: int
    terminal_id: Optional[int] = None
    vessel_id: Optional[int] = None
    bl_number: Optional[str] = None
    booking_number: Optional[str] = None
    reference: Optional[str] = None
    eta: Optional[datetime] = None
    bl_released: bool = False
    internal_note: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class DeliveryOrderDetailResponseSchema(DeliveryOrderResponseSchema):
    customer: CustomerNestedSchema
    terminal: Optional[TerminalNestedSchema] = None
    vessel: Optional[VesselNestedSchema] = None
    containers: List[ContainerResponseSchema] = []
    files: List[FileNestedSchema] = []


class DeliveryOrderDeleteResponseSchema(DeliveryOrderResponseSchema):
    # delete 후 entity 반환 — `is_active=False` 가 들어옴
    pass
```

---

## 7. PR 리뷰 체크리스트 (이 도메인 / 비슷한 패턴 도메인)

- [ ] 헤더에 `(Base, TeamScopedMixin)`
- [ ] 라인 (container) 은 별도 폴더 + `__with_team_rel__ = False` + 복합 FK
- [ ] 상태 enum 은 `<domain>/const/status.py` + `SAEnum(EnumClass, name="...")`
- [ ] 상태 전이 로직은 `state_machine.py` 분리
- [ ] `assert_can_transition(ctx, target, force=...)` 통과 후 status 업데이트
- [ ] WS event — 일반 update 와 transition 구분 (`<domain>.updated` vs `<domain>.status.changed`)
- [ ] transition payload 에 `previous_status`, `target_status`, `reason` 포함
- [ ] `dispatch` / `complete` 같은 편의 메서드 — service 명시적 이름 + router 명시적 path (옵션)
- [ ] bulk 메서드 — partial failure 처리 (`failed: List[BulkFailureItem]`)
- [ ] permission code: `DO_WRITE` / `DO_DISPATCH` / `DO_COMPLETE` 등 액션별 분리
- [ ] 라우터 순서: `/sync` → `/{do_id}` (path param)
- [ ] Bulk 라우터는 `permission_guard(DO_WRITE)` + 옵션으로 `BULK_OPERATION_LIMIT` 검증

---

## 8. 관련 문서

- [`../team/CLAUDE.md`](../team/CLAUDE.md) — 표준 도메인 규약 (모든 도메인의 베이스)
- [`../common/pagination/CLAUDE.md`](../common/pagination/CLAUDE.md) — 페이징 / DELETE / WS / sync
- [`../common/repository/CLAUDE.md`](../common/repository/CLAUDE.md) — TeamScopedRepoMixin
- [`../rbac/CLAUDE.md`](../rbac/CLAUDE.md) — `DO_WRITE`, `DO_DISPATCH` 등 코드 + role 가드
- [`../driver_mobile/CLAUDE.md`](../driver_mobile/CLAUDE.md) — driver 가 leg 통해 D/O 진행 보고하는 흐름
- (향후) `../leg/CLAUDE.md` — leg state machine (비슷한 패턴)
- (향후) `../settlement/CLAUDE.md` — settlement state machine
