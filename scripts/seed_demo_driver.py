# scripts/seed_demo_driver.py
"""투자자 데모용 — 김기사 + 풍부한 운송 데이터 시드.

전제: `seed_local.py` 가 먼저 실행되어 team "TMS Demo" + admin/dispatcher 가 있음.

생성:
  - User "김기사" (phone="01012345678", role=DRIVER) — 폰번호 OTP 로그인용
  - Driver (Truck "12가 3456", 1톤 카고)
  - Customer 5개 (한국 화주)
  - Location 6개 (서울 강남, 인천 남동, 경기 성남, 부산 사하, 평택항, 의왕 ICD)
  - DeliveryOrder 6건:
    · 1건 — pending offer (홈 진입 3초 후 알림으로 띄울 새 배차)
    · 1건 — in_progress (홈의 진행 중 카드)
    · 4건 — completed (운행 이력)
  - Container — D/O 마다 1개
  - Leg — D/O 마다 1개 (driver_id = 김기사)
  - Settlement — completed leg 마다 (총 15+ 건이 되도록 추가 더미 운행 + 정산)
  - ChatMessage — 5건 자연스러운 한국어 대화

사용:
  PYTHONPATH=src python scripts/seed_demo_driver.py

Idempotent — 김기사 phone 으로 이미 user 가 있으면 모든 단계 skip.
"""
from __future__ import annotations

import asyncio
import sys
import random
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import common.model.models_registry  # noqa: F401

from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from auth.const.providers import AuthProviderEnum
from chat.const.sender import ChatSenderType
from chat.model import ChatMessageModel
from common.const.settings import settings
from container.model import ContainerModel
from container.const.status import ContainerSize
from customer.model import CustomerModel
from customer.const.status import PartnerKind
from database.mysql_connection import write_engine
from delivery_order.model import DeliveryOrderModel
from delivery_order.const.status import DeliveryStatus, ShipmentDirection
from driver.model import DriverModel
from driver.const.status import DutyStatus, EmploymentKind
from leg.model import LegModel
from leg.const.status import LegStatus, MoveType, ServiceType
from location.model import LocationModel
from location.const.kind import LocationKind
from rbac.model import PermissionGroupModel
from settlement.model import SettlementModel
from settlement.const.status import SettlementStatus
from team.model import TeamModel, UserTeamModel
from truck.model import TruckModel
from user.const.roles import RolesEnum
from user.model import UserModel


TEAM_NAME = "TMS Demo"
DRIVER_PHONE = "01012345678"
DRIVER_PASSWORD = "Driver!1"


# ── helpers ──────────────────────────────────────────────────

async def get_team(db) -> TeamModel:
    team = (await db.execute(
        select(TeamModel).where(TeamModel.name == TEAM_NAME)
    )).scalar_one_or_none()
    if not team:
        raise RuntimeError(
            f"team '{TEAM_NAME}' 없음. 먼저 seed_local.py 실행."
        )
    return team


async def get_admin_perm_group(db, team: TeamModel) -> PermissionGroupModel | None:
    return (await db.execute(
        select(PermissionGroupModel).where(
            PermissionGroupModel.team_id == team.id,
            PermissionGroupModel.system_key == "ADMIN",
        )
    )).scalar_one_or_none()


async def get_or_create_driver_user(db, team: TeamModel) -> UserModel:
    existing = (await db.execute(
        select(UserModel).where(UserModel.phone == DRIVER_PHONE)
    )).scalar_one_or_none()
    if existing:
        print(f"[skip] user 김기사 (id={existing.id})")
        return existing

    pw_hash = bcrypt.using(rounds=settings.BCRYPT_ROUNDS).hash(DRIVER_PASSWORD)
    u = UserModel(
        email=None,
        password=pw_hash,
        auth_provider=AuthProviderEnum.EMAIL.value,
        role=RolesEnum.DRIVER,
        name="김기사",
        phone=DRIVER_PHONE,
    )
    db.add(u)
    await db.flush()
    print(f"[new]  user 김기사 (id={u.id}, phone={DRIVER_PHONE})")

    # 팀 멤버십
    pg = await get_admin_perm_group(db, team)
    db.add(UserTeamModel(
        user_id=u.id, team_id=team.id,
        permission_group_id=pg.id if pg else None,
    ))
    await db.flush()
    return u


async def get_or_create_truck(db, team: TeamModel) -> TruckModel:
    existing = (await db.execute(
        select(TruckModel).where(
            TruckModel.team_id == team.id,
            TruckModel.plate_no == "12가 3456",
        )
    )).scalar_one_or_none()
    if existing:
        print(f"[skip] truck 12가3456 (id={existing.id})")
        return existing
    t = TruckModel(
        team_id=team.id,
        plate_no="12가 3456",
        make="현대",
        model="포터2 1톤 카고",
    )
    db.add(t)
    await db.flush()
    print(f"[new]  truck 12가3456 (id={t.id})")
    return t


async def get_or_create_driver_row(db, team: TeamModel, user: UserModel, truck: TruckModel) -> DriverModel:
    existing = (await db.execute(
        select(DriverModel).where(
            DriverModel.team_id == team.id,
            DriverModel.user_id == user.id,
        )
    )).scalar_one_or_none()
    if existing:
        print(f"[skip] driver 김기사 (id={existing.id})")
        return existing
    d = DriverModel(
        team_id=team.id,
        user_id=user.id,
        license_number="11-22-345678-90",
        license_expires_at=date(2027, 12, 31),
        employment_kind=EmploymentKind.IN_HOUSE,
        duty_status=DutyStatus.ON_DUTY,
        duty_changed_at=datetime.now(timezone.utc) - timedelta(hours=2),
        default_truck_id=truck.id,
    )
    db.add(d)
    await db.flush()
    print(f"[new]  driver 김기사 (id={d.id})")
    return d


KOREAN_CUSTOMERS = [
    ("(주)한진해운물류", "12-345-67890", "02-1234-5678"),
    ("쿠팡로지스틱스", "21-098-76543", "02-2345-6789"),
    ("CJ대한통운",     "30-987-65432", "02-3456-7890"),
    ("롯데글로벌로지스", "40-876-54321", "02-4567-8901"),
    ("HMM해운(주)",    "50-765-43210", "02-5678-9012"),
]

async def seed_customers(db, team: TeamModel) -> list[CustomerModel]:
    out = []
    for name, biz_no, phone in KOREAN_CUSTOMERS:
        existing = (await db.execute(
            select(CustomerModel).where(
                CustomerModel.team_id == team.id,
                CustomerModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            print(f"[skip] customer {name} (id={existing.id})")
            continue
        c = CustomerModel(
            team_id=team.id,
            name=name,
            kind=PartnerKind.CUSTOMER,
            contact_name="담당자",
            contact_phone=phone,
        )
        db.add(c)
        await db.flush()
        out.append(c)
        print(f"[new]  customer {name} (id={c.id})")
    return out


KOREAN_LOCATIONS = [
    # (name, address, lat, lng, kind)
    ("강남구 물류센터",         "서울특별시 강남구 테헤란로 152",       37.500, 127.036, LocationKind.CUSTOMER),
    ("판교 IT 물류 허브",         "경기도 성남시 분당구 판교역로 235",     37.395, 127.111, LocationKind.CUSTOMER),
    ("인천 남동공단 창고",         "인천광역시 남동구 남동대로 215",         37.447, 126.731, LocationKind.CUSTOMER),
    ("부산항 BPT 터미널",          "부산광역시 사하구 신항북로 80",           35.083, 128.815, LocationKind.PORT),
    ("평택항 동부두 야드",         "경기도 평택시 포승읍 평택항만길 250",   36.964, 126.834, LocationKind.PORT),
    ("의왕 ICD 컨테이너 야드",     "경기도 의왕시 이미로 40",                 37.343, 126.967, LocationKind.YARD),
]

async def seed_locations(db, team: TeamModel) -> list[LocationModel]:
    out = []
    for name, addr, lat, lng, kind in KOREAN_LOCATIONS:
        existing = (await db.execute(
            select(LocationModel).where(
                LocationModel.team_id == team.id,
                LocationModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            print(f"[skip] location {name} (id={existing.id})")
            continue
        l = LocationModel(
            team_id=team.id,
            name=name,
            kind=kind,
            address=addr,
            latitude=Decimal(str(lat)),
            longitude=Decimal(str(lng)),
        )
        db.add(l)
        await db.flush()
        out.append(l)
        print(f"[new]  location {name} (id={l.id})")
    return out


async def seed_delivery_orders(
    db, team: TeamModel, customers: list[CustomerModel], locations: list[LocationModel],
    driver_row: DriverModel, truck: TruckModel,
):
    """6+ D/O 생성 — 다양한 상태로."""
    now = datetime.now(timezone.utc)
    pickup_l = locations[0]   # 강남구
    deliver_l = locations[2]  # 인천 남동

    # 이미 데모 D/O 가 있으면 skip
    existing_count = (await db.execute(
        select(DeliveryOrderModel).where(
            DeliveryOrderModel.team_id == team.id,
            DeliveryOrderModel.internal_note.like("%[DEMO-DRIVER]%"),
        )
    )).scalars().all()
    if len(existing_count) > 0:
        print(f"[skip] DEMO-DRIVER D/O 이미 {len(existing_count)} 건 존재")
        return

    do_specs = [
        # (status, bl_suffix, customer_idx, pickup_idx, deliver_idx, offset_hours, label)
        ("PENDING_OFFER", "PEND-0501", 0, 0, 2, 0,    "신규 배차 (수락 대기)"),
        ("IN_PROGRESS",   "PROG-0501", 1, 0, 3, -3,   "진행 중"),
        ("COMPLETED",     "COMP-0429", 2, 0, 4, -24,  "어제 완료"),
        ("COMPLETED",     "COMP-0428", 3, 1, 2, -48,  "이틀 전 완료"),
        ("COMPLETED",     "COMP-0427", 4, 2, 5, -72,  "사흘 전 완료"),
        ("COMPLETED",     "COMP-0426", 0, 3, 5, -96,  "나흘 전 완료"),
    ]

    # 추가 12 건 completed (정산 15~20 채우기 위해)
    for i in range(12):
        do_specs.append((
            "COMPLETED",
            f"COMP-04{20-i:02d}",
            i % len(customers),
            i % len(locations),
            (i + 2) % len(locations),
            -120 - i * 24,
            f"{i+5}일 전 완료",
        ))

    do_status_map = {
        "PENDING_OFFER": DeliveryStatus.DISPATCHED,
        "IN_PROGRESS":   DeliveryStatus.DISPATCHED,
        "COMPLETED":     DeliveryStatus.COMPLETED,
    }
    leg_status_map = {
        "PENDING_OFFER": LegStatus.PENDING,
        "IN_PROGRESS":   LegStatus.IN_TRANSIT,
        "COMPLETED":     LegStatus.COMPLETED,
    }

    for kind, bl_suffix, cust_idx, p_idx, d_idx, hour_offset, label in do_specs:
        cust = customers[cust_idx % len(customers)]
        pl   = locations[p_idx % len(locations)]
        dl   = locations[d_idx % len(locations)]
        base_time = now + timedelta(hours=hour_offset)

        do = DeliveryOrderModel(
            team_id=team.id,
            status=do_status_map[kind],
            direction=ShipmentDirection.IMPORT,
            customer_id=cust.id,
            bl_number=f"HJSCSE-{bl_suffix}",
            booking_number=f"BK{bl_suffix}",
            reference=f"REF-{bl_suffix}",
            eta=base_time + timedelta(hours=2),
            bl_released=(kind == "COMPLETED"),
            internal_note=f"[DEMO-DRIVER] {label}",
        )
        db.add(do)
        await db.flush()

        # 컨테이너 1개
        cont = ContainerModel(
            team_id=team.id,
            delivery_order_id=do.id,
            sequence_no=1,
            container_number=f"HJCU{1000000 + do.id:07d}",
            size=ContainerSize.SIZE_40HC,
            service_type=ServiceType.LIVE,
        )
        db.add(cont)
        await db.flush()
        container_id = cont.id

        # leg 1개
        leg_kwargs = {
            "team_id": team.id,
            "delivery_order_id": do.id,
            "container_id": container_id,
            "step": do_status_map[kind],
            "move_type": MoveType.LOADED,
            "service_type": ServiceType.LIVE,
            "status": leg_status_map[kind],
            "driver_id": driver_row.id,
            "truck_id": truck.id,
            "pickup_location_id": pl.id,
            "delivery_location_id": dl.id,
            "pickup_date": base_time,
            "delivery_date": base_time + timedelta(hours=2),
        }
        if kind == "PENDING_OFFER":
            leg_kwargs["offered_at"] = now - timedelta(minutes=2)
        elif kind == "IN_PROGRESS":
            leg_kwargs["offered_at"] = now - timedelta(hours=4)
            leg_kwargs["accepted_at"] = now - timedelta(hours=3, minutes=50)
            leg_kwargs["started_at"] = now - timedelta(hours=3)
        elif kind == "COMPLETED":
            leg_kwargs["offered_at"] = base_time - timedelta(hours=1)
            leg_kwargs["accepted_at"] = base_time - timedelta(minutes=55)
            leg_kwargs["started_at"] = base_time
            leg_kwargs["completed_at"] = base_time + timedelta(hours=2)

        leg = LegModel(**leg_kwargs)
        db.add(leg)
        await db.flush()

        # completed 만 settlement 생성
        if kind == "COMPLETED":
            amount = Decimal(random.choice([
                85_000, 120_000, 150_000, 180_000, 210_000, 245_000, 280_000,
            ]))
            # 정산 상태: 이틀 전 이상 → APPROVED (완료), 그 이후 → CALCULATED (대기)
            is_old = hour_offset < -48
            status_enum = SettlementStatus.APPROVED if is_old else SettlementStatus.CALCULATED
            settle = SettlementModel(
                team_id=team.id,
                leg_id=leg.id,
                settlement_status=status_enum,
                system_total=amount,
                final_amount=amount,
                is_settled=is_old,
                approved_at=(base_time + timedelta(hours=3)) if is_old else None,
            )
            db.add(settle)

        print(f"[new]  D/O {bl_suffix} ({label}, leg={leg.id})")

    await db.flush()


CHAT_DIALOGUES = [
    (ChatSenderType.DISPATCHER, "기사님, 오늘 첫 배차 잘 부탁드립니다.", -180),
    (ChatSenderType.DRIVER,     "네, 출발합니다.", -175),
    (ChatSenderType.DISPATCHER, "도착하시면 사진 잊지마세요.", -170),
    (ChatSenderType.DRIVER,     "확인했습니다. 가는 길에 정체가 좀 있어서 10분 지연 예상돼요.", -120),
    (ChatSenderType.DISPATCHER, "네, 안전 운행 부탁드립니다.", -115),
]

async def seed_chat(db, team: TeamModel, driver_user: UserModel):
    existing = (await db.execute(
        select(ChatMessageModel).where(
            ChatMessageModel.team_id == team.id,
            ChatMessageModel.driver_user_id == driver_user.id,
        )
    )).scalars().all()
    if existing:
        print(f"[skip] chat ({len(existing)} 건 이미 존재)")
        return

    now = datetime.now(timezone.utc)
    for sender, content, minutes_ago in CHAT_DIALOGUES:
        msg = ChatMessageModel(
            team_id=team.id,
            driver_user_id=driver_user.id,
            sender_type=sender,
            sender_user_id=driver_user.id if sender == ChatSenderType.DRIVER else None,
            content=content,
            created_at=now + timedelta(minutes=minutes_ago),
        )
        db.add(msg)
    await db.flush()
    print(f"[new]  chat 메시지 {len(CHAT_DIALOGUES)} 건")


# ── main ─────────────────────────────────────────────────────

async def main():
    Session = async_sessionmaker(write_engine, expire_on_commit=False)
    async with Session() as db:
        team = await get_team(db)
        truck = await get_or_create_truck(db, team)
        driver_user = await get_or_create_driver_user(db, team)
        driver_row = await get_or_create_driver_row(db, team, driver_user, truck)
        customers = await seed_customers(db, team)
        locations = await seed_locations(db, team)
        await seed_delivery_orders(db, team, customers, locations, driver_row, truck)
        await seed_chat(db, team, driver_user)
        await db.commit()
        print()
        print("═" * 60)
        print("✓ 데모 시드 완료")
        print(f"  team: {team.name} (id={team.id})")
        print(f"  김기사: phone={DRIVER_PHONE}, password={DRIVER_PASSWORD}")
        print(f"  로그인: POST /api/v1/auth/driver/otp/request → verify → login")
        print(f"  (데모: OTP 는 콘솔 출력 확인)")
        print("═" * 60)


if __name__ == "__main__":
    asyncio.run(main())
