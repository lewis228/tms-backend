# scripts/seed_demo.py
"""
데모 데이터 시드 스크립트 — test@test.com 이 보고 만질 수 있는 풍부한 샘플.

전제: seed_local.py 가 먼저 실행되어 team "TMS Demo" + 5명 user + admin perm group 이 있음.

생성:
  - customer 12개
  - terminal 8개
  - vessel 10개
  - location 15개
  - driver 8개 (user 도 같이)
  - rate_setting 6개
  - delivery_order 24개 (다양한 status)
  - leg ~50개 (D/O 별 2-3개)
  - settlement 12개 (CALCULATED / ADJUSTED / APPROVED 섞음)
  - notification 15개
  - api_key 3개

사용:
  PYTHONPATH=src python scripts/seed_demo.py

Idempotent: 같은 name 으로 이미 존재하는 row 는 skip.
"""
from __future__ import annotations

import asyncio
import secrets
import sys
import random
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import common.model.models_registry  # noqa: F401

from passlib.hash import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from auth.const.providers import AuthProviderEnum
from common.const.settings import settings
from database.mysql_connection import write_engine
from customer.model import CustomerModel
from terminal.model import TerminalModel
from vessel.model import VesselModel
from location.model import LocationModel
from location.const.kind import LocationKind
from driver.model import DriverModel
from rate_setting.model import RateSettingModel
from rate_setting.const.rate_type import RateType
from delivery_order.model import DeliveryOrderModel
from delivery_order.const.status import DeliveryStatus, ShipmentDirection, ContainerSize
from leg.model import LegModel
from leg.const.status import LegStatus, MoveType, ServiceType
from settlement.model import SettlementModel
from settlement.const.status import SettlementStatus
from notification.model import NotificationModel
from notification.const.channel import NotificationChannel, NotificationStatus
from api_key.model import ApiKeyModel
from team.model import TeamModel
from user.const.roles import RolesEnum
from user.model import UserModel


TEAM_NAME = "TMS Demo"
PASSWORD = "Password!1"

random.seed(42)  # 같은 데이터 재현


# ──────────────────────────────────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def days(n: int) -> datetime:
    return now_utc() + timedelta(days=n)


async def get_team(db) -> TeamModel:
    t = (await db.execute(
        select(TeamModel).where(TeamModel.name == TEAM_NAME)
    )).scalar_one_or_none()
    if not t:
        print(f"[err] team '{TEAM_NAME}' 없음. seed_local.py 먼저 실행")
        sys.exit(1)
    return t


# ──────────────────────────────────────────────────────────────────────────
# 도메인별 시드
# ──────────────────────────────────────────────────────────────────────────

CUSTOMERS = [
    ("Acme Logistics", "ACME", "1100 Trade St, Long Beach CA 90802", "Sarah Kim", "sarah@acme.example"),
    ("Pacific Imports", "PAC", "2400 Ocean Blvd, San Pedro CA 90731", "John Lee", "john@pacific.example"),
    ("Bluewave Freight", "BLUE", "550 Wilmington Ave, Wilmington CA 90744", "Mike Chen", "mike@bluewave.example"),
    ("Coastline Distribution", "COAST", "3200 Carson St, Carson CA 90745", "Anna Park", "anna@coastline.example"),
    ("Global Trade Co", "GTC", "1500 Harbor Dr, Long Beach CA 90802", "Daniel Tan", "daniel@gtc.example"),
    ("Sunrise Forwarding", "SUN", "780 Atlantic Ave, Long Beach CA 90802", "Rachel Park", "rachel@sunrise.example"),
    ("Westport Logistics", "WEST", "440 Anaheim St, Wilmington CA 90744", "Brian Cho", "brian@westport.example"),
    ("Anchor Shipping", "ANCH", "9000 Alameda St, Los Angeles CA 90002", "Christopher Yu", "chris@anchor.example"),
    ("Harbor Light Trading", "HLT", "1200 Marine Way, Wilmington CA 90744", "Helen Jang", "helen@hltrade.example"),
    ("Pacific Crest Cargo", "PCC", "5600 Pier B St, Long Beach CA 90802", "Sam Park", "sam@pcc.example"),
    ("Cascade Carriers Inc", "CCI", "2200 Avalon Blvd, Wilmington CA 90744", "Jenny Lim", "jenny@cascade.example"),
    ("Liberty Forwarders", "LIB", "1800 Henry Ford Ave, Wilmington CA 90744", "Ethan Han", "ethan@liberty.example"),
]

TERMINALS = [
    ("APM Terminals Pier 400", "APM", "2500 Navy Way, Terminal Island, CA 90731", 33.7414, -118.2473),
    ("Yusen Terminals YTI", "YTI", "701 New Dock St, Terminal Island, CA 90731", 33.7400, -118.2630),
    ("Total Terminals International", "TTI", "1521 Pier T Ave, Long Beach, CA 90802", 33.7330, -118.2080),
    ("Pacific Container Terminal", "PCT", "1521 Pier J Ave, Long Beach, CA 90802", 33.7290, -118.2255),
    ("Long Beach Container Terminal", "LBCT", "201 S. Pico Ave, Long Beach, CA 90802", 33.7567, -118.2226),
    ("ITS Terminal", "ITS", "1281 Pier G St, Long Beach, CA 90802", 33.7387, -118.2148),
    ("Fenix Marine Services", "FMS", "624 Terminal Way, San Pedro, CA 90731", 33.7479, -118.2734),
    ("West Basin Container", "WBCT", "2050 John S Gibson Blvd, San Pedro, CA 90731", 33.7488, -118.2647),
]

VESSELS = [
    ("MSC GULSUN", "9839272", "MSC"),
    ("EVER GIVEN", "9811000", "EVERGREEN"),
    ("HMM ALGECIRAS", "9863297", "HMM"),
    ("ONE INNOVATION", "9788055", "ONE"),
    ("CMA CGM JACQUES SAADE", "9839183", "CMA CGM"),
    ("COSCO UNIVERSE", "9795639", "COSCO"),
    ("MAERSK MC-KINNEY MOLLER", "9619919", "MAERSK"),
    ("OOCL HONG KONG", "9776171", "OOCL"),
    ("YANG MING WORLD", "9869225", "YANG MING"),
    ("HAPAG-LLOYD AFRICA", "9450325", "HAPAG-LLOYD"),
]

LOCATIONS = [
    ("Acme LA Warehouse", LocationKind.CUSTOMER, "1100 Trade St, Long Beach CA 90802", 33.7615, -118.1959),
    ("Acme Distribution Center", LocationKind.CUSTOMER, "2400 E 26th St, Vernon CA 90058", 34.0090, -118.2253),
    ("Pacific Imports Yard", LocationKind.CUSTOMER, "2400 Ocean Blvd, San Pedro CA 90731", 33.7372, -118.2925),
    ("Bluewave Carson Hub", LocationKind.CUSTOMER, "550 Wilmington Ave, Carson CA 90744", 33.8010, -118.2410),
    ("Coastline Carson DC", LocationKind.CUSTOMER, "3200 Carson St, Carson CA 90745", 33.8316, -118.2628),
    ("GTC Long Beach Yard", LocationKind.CUSTOMER, "1500 Harbor Dr, Long Beach CA 90802", 33.7625, -118.2143),
    ("Sunrise Wilmington", LocationKind.CUSTOMER, "780 Atlantic Ave, Long Beach CA 90802", 33.7841, -118.1853),
    ("Westport Wilmington Yard", LocationKind.CUSTOMER, "440 Anaheim St, Wilmington CA 90744", 33.7787, -118.2728),
    ("Anchor Vernon DC", LocationKind.CUSTOMER, "9000 Alameda St, Los Angeles CA 90002", 33.9544, -118.2275),
    ("Harbor Light Wilmington", LocationKind.CUSTOMER, "1200 Marine Way, Wilmington CA 90744", 33.7700, -118.2745),
    ("Empty Yard #1 — Compton", LocationKind.YARD, "1500 Compton Blvd, Compton CA 90220", 33.8950, -118.2210),
    ("Empty Yard #2 — Long Beach", LocationKind.YARD, "1700 Pier S Ave, Long Beach CA 90802", 33.7510, -118.2450),
    ("Cascade Yard", LocationKind.YARD, "2200 Avalon Blvd, Wilmington CA 90744", 33.7903, -118.2660),
    ("Port of Long Beach Gate", LocationKind.PORT, "1 Pico Ave, Long Beach CA 90802", 33.7530, -118.2270),
    ("Port of Los Angeles Gate", LocationKind.PORT, "425 S Palos Verdes St, San Pedro CA 90731", 33.7414, -118.2840),
]

DRIVERS = [
    ("Carlos Mendoza", "carlos.mendoza@drv.demo", "+1-310-555-0101", "D7842918", "CA", "TRK-101"),
    ("James Park", "james.park@drv.demo", "+1-310-555-0102", "D6651223", "CA", "TRK-102"),
    ("Miguel Hernandez", "miguel.h@drv.demo", "+1-310-555-0103", "D9012445", "CA", "TRK-103"),
    ("David Choi", "david.choi@drv.demo", "+1-310-555-0104", "D5543119", "CA", "TRK-104"),
    ("Roberto Silva", "roberto.s@drv.demo", "+1-310-555-0105", "D8826110", "CA", "TRK-105"),
    ("Tom Anderson", "tom.a@drv.demo", "+1-310-555-0106", "D3344219", "CA", "TRK-106"),
    ("Henry Wong", "henry.wong@drv.demo", "+1-310-555-0107", "D7799112", "CA", "TRK-107"),
    ("Alex Reyes", "alex.reyes@drv.demo", "+1-310-555-0108", "D2211008", "CA", "TRK-108"),
]

RATE_SETTINGS = [
    ("LA/LB Local Drayage Flat", RateType.FLAT_RATE, Decimal("250.00"), None, None, "LA/LB 권역 단일 운송"),
    ("LA/LB Long-haul Per Mile", RateType.PER_MILE, None, None, Decimal("3.50"), "장거리 마일당 요율"),
    ("Inland Empire Flat", RateType.FLAT_RATE, Decimal("450.00"), None, None, "Riverside / San Bernardino 권역"),
    ("Per-diem Surcharge %", RateType.PERCENTAGE, None, Decimal("0.0500"), None, "체화료에 대한 5% surcharge"),
    ("Premium Same-day Rate", RateType.FLAT_RATE, Decimal("750.00"), None, None, "당일 처리 프리미엄"),
    ("Empty Return Shuttle", RateType.PER_MILE, None, None, Decimal("2.20"), "빈 컨테이너 반납 shuttle"),
]


# ──────────────────────────────────────────────────────────────────────────
# 시드 함수들
# ──────────────────────────────────────────────────────────────────────────

async def seed_customers(db, team: TeamModel) -> list[CustomerModel]:
    out = []
    for name, code, addr, contact, email in CUSTOMERS:
        existing = (await db.execute(
            select(CustomerModel).where(
                CustomerModel.team_id == team.id,
                CustomerModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        c = CustomerModel(
            team_id=team.id, name=name, code=code,
            billing_address=addr, contact_name=contact,
            contact_email=email,
            contact_phone=f"+1-562-555-{random.randint(1000, 9999)}",
        )
        db.add(c)
        await db.flush()
        out.append(c)
    print(f"[customer] {len(out)}")
    return out


async def seed_terminals(db, team: TeamModel) -> list[TerminalModel]:
    out = []
    for name, code, addr, lat, lng in TERMINALS:
        existing = (await db.execute(
            select(TerminalModel).where(
                TerminalModel.team_id == team.id,
                TerminalModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        t = TerminalModel(
            team_id=team.id, name=name, code=code, address=addr,
            latitude=Decimal(str(lat)), longitude=Decimal(str(lng)),
        )
        db.add(t)
        await db.flush()
        out.append(t)
    print(f"[terminal] {len(out)}")
    return out


async def seed_vessels(db, team: TeamModel) -> list[VesselModel]:
    out = []
    for name, imo, line in VESSELS:
        existing = (await db.execute(
            select(VesselModel).where(
                VesselModel.team_id == team.id,
                VesselModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        v = VesselModel(team_id=team.id, name=name, imo_number=imo, line=line)
        db.add(v)
        await db.flush()
        out.append(v)
    print(f"[vessel] {len(out)}")
    return out


async def seed_locations(
    db, team: TeamModel, customers: list[CustomerModel],
) -> list[LocationModel]:
    out = []
    for i, (name, kind, addr, lat, lng) in enumerate(LOCATIONS):
        existing = (await db.execute(
            select(LocationModel).where(
                LocationModel.team_id == team.id,
                LocationModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        # 첫 customer 들에 일부 location 매핑 (customer warehouse 류)
        cust_id = customers[i % len(customers)].id if kind == LocationKind.CUSTOMER else None
        l = LocationModel(
            team_id=team.id, name=name, kind=kind, address=addr,
            latitude=Decimal(str(lat)), longitude=Decimal(str(lng)),
            customer_id=cust_id,
        )
        db.add(l)
        await db.flush()
        out.append(l)
    print(f"[location] {len(out)}")
    return out


async def seed_drivers(db, team: TeamModel) -> list[DriverModel]:
    out = []
    for name, email, phone, license_no, state, truck in DRIVERS:
        # user 먼저 (drv.demo 도메인은 SMTP rejection 안 하는 도메인 — 이미 .dev 와 같은 형태)
        user = (await db.execute(
            select(UserModel).where(UserModel.email == email)
        )).scalar_one_or_none()
        if not user:
            pw_hash = bcrypt.using(rounds=settings.BCRYPT_ROUNDS).hash(PASSWORD)
            user = UserModel(
                email=email, password=pw_hash,
                auth_provider=AuthProviderEnum.EMAIL.value,
                role=RolesEnum.DRIVER, name=name, phone=phone,
            )
            db.add(user)
            await db.flush()

        # driver row
        existing = (await db.execute(
            select(DriverModel).where(
                DriverModel.team_id == team.id,
                DriverModel.user_id == user.id,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        d = DriverModel(
            team_id=team.id, user_id=user.id,
            license_number=license_no, license_state=state, truck_number=truck,
        )
        db.add(d)
        await db.flush()
        out.append(d)
    print(f"[driver] {len(out)}")
    return out


async def seed_rate_settings(db, team: TeamModel) -> list[RateSettingModel]:
    out = []
    for name, rate_type, flat, pct, per_mile, desc in RATE_SETTINGS:
        existing = (await db.execute(
            select(RateSettingModel).where(
                RateSettingModel.team_id == team.id,
                RateSettingModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        r = RateSettingModel(
            team_id=team.id, name=name, rate_type=rate_type,
            flat_amount=flat, rate_percent=pct, rate_per_mile=per_mile,
            effective_date=date.today() - timedelta(days=30),
            description=desc,
        )
        db.add(r)
        await db.flush()
        out.append(r)
    print(f"[rate_setting] {len(out)}")
    return out


CONTAINER_SIZES = list(ContainerSize)
DO_STATUSES = list(DeliveryStatus)


async def seed_delivery_orders(
    db, team: TeamModel,
    customers: list[CustomerModel],
    terminals: list[TerminalModel],
    vessels: list[VesselModel],
    locations: list[LocationModel],
) -> list[DeliveryOrderModel]:
    customer_locs = [l for l in locations if l.kind == LocationKind.CUSTOMER]
    yards = [l for l in locations if l.kind == LocationKind.YARD]

    out = []
    NUM_DO = 24
    for i in range(NUM_DO):
        bl = f"MSCU{1000000 + i:07d}"
        existing = (await db.execute(
            select(DeliveryOrderModel).where(
                DeliveryOrderModel.team_id == team.id,
                DeliveryOrderModel.bl_number == bl,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue

        cust = customers[i % len(customers)]
        term = terminals[i % len(terminals)]
        vess = vessels[i % len(vessels)]
        delivery_loc = customer_locs[i % len(customer_locs)]
        return_loc = yards[i % len(yards)]
        size = CONTAINER_SIZES[i % len(CONTAINER_SIZES)]

        # 진행 단계 분포 — 다양한 상태로
        if i < 4:
            status = DeliveryStatus.PLANNING
            container_no = None
        elif i < 8:
            status = DeliveryStatus.DISPATCHED
            container_no = f"MSCU{2000000 + i:07d}"
        elif i < 12:
            status = DeliveryStatus.YARD_STAGED
            container_no = f"MSCU{2000000 + i:07d}"
        elif i < 16:
            status = DeliveryStatus.FINAL_DELIVERY
            container_no = f"MSCU{2000000 + i:07d}"
        elif i < 20:
            status = DeliveryStatus.EMPTY_STAGED
            container_no = f"MSCU{2000000 + i:07d}"
        else:
            status = DeliveryStatus.COMPLETED
            container_no = f"MSCU{2000000 + i:07d}"

        direction = ShipmentDirection.IMPORT if i % 3 != 0 else ShipmentDirection.EXPORT

        do = DeliveryOrderModel(
            team_id=team.id,
            status=status, direction=direction,
            bl_number=bl, booking_number=f"BKG{500000 + i:06d}",
            reference=f"REF-2026-{i + 1:03d}",
            customer_id=cust.id,
            terminal_id=term.id,
            vessel_id=vess.id,
            delivery_location_id=delivery_loc.id,
            return_location_id=return_loc.id,
            container_number=container_no,
            container_size=size,
            container_type="DRY",
            chassis_number=f"CHS{100000 + i:06d}" if i % 2 == 0 else None,
            eta=days(-3 + i % 10),
            pickup_appointment=days(i % 7),
            delivery_appointment=days(1 + i % 5),
            return_appointment=days(3 + i % 5),
            demurrage_lfd=(date.today() + timedelta(days=2 + i % 5)),
            detention_lfd=(date.today() + timedelta(days=5 + i % 5)),
            bl_released=(i % 2 == 0),
            pier_pass_paid=(i % 3 == 0),
            customs_cleared=(i % 4 == 0),
        )
        db.add(do)
        await db.flush()
        out.append(do)

    print(f"[delivery_order] {len(out)}")
    return out


async def seed_legs(
    db, team: TeamModel,
    delivery_orders: list[DeliveryOrderModel],
    drivers: list[DriverModel],
    locations: list[LocationModel],
) -> list[LegModel]:
    out = []
    customer_locs = [l for l in locations if l.kind == LocationKind.CUSTOMER]
    yards = [l for l in locations if l.kind == LocationKind.YARD]
    ports = [l for l in locations if l.kind == LocationKind.PORT]

    for do in delivery_orders:
        # 이미 leg 가 있으면 skip
        existing_count = (await db.execute(
            select(LegModel).where(
                LegModel.team_id == team.id,
                LegModel.delivery_order_id == do.id,
            )
        )).scalars().all()
        if existing_count:
            out.extend(existing_count)
            continue

        # D/O 상태에 따라 leg 들 생성
        # YARD_STAGED leg (port → yard)
        steps = []
        if do.direction == ShipmentDirection.IMPORT:
            # IMPORT: port → yard? → customer → empty yard
            steps = [
                (DeliveryStatus.YARD_STAGED, ports[0] if ports else None, yards[0] if yards else None, MoveType.LOADED, ServiceType.DROP),
                (DeliveryStatus.FINAL_DELIVERY, yards[0] if yards else None, customer_locs[0], MoveType.LOADED, ServiceType.LIVE),
                (DeliveryStatus.EMPTY_STAGED, customer_locs[0], yards[1 % len(yards)] if len(yards) > 1 else yards[0], MoveType.EMPTY, ServiceType.DROP),
            ]
        else:
            # EXPORT: yard (empty) → customer (load) → port
            steps = [
                (DeliveryStatus.YARD_STAGED, yards[0] if yards else None, customer_locs[0], MoveType.EMPTY, ServiceType.DROP),
                (DeliveryStatus.FINAL_DELIVERY, customer_locs[0], ports[0] if ports else None, MoveType.LOADED, ServiceType.DROP),
            ]

        for idx, (step, pickup, delivery, move_type, service_type) in enumerate(steps):
            # leg 상태 결정 — D/O 상태 기준
            if do.status in (DeliveryStatus.PLANNING,):
                leg_status = LegStatus.PENDING
                driver = None
            elif do.status == DeliveryStatus.DISPATCHED:
                leg_status = LegStatus.PENDING
                driver = drivers[idx % len(drivers)]
            elif do.status == DeliveryStatus.YARD_STAGED and step != DeliveryStatus.YARD_STAGED:
                leg_status = LegStatus.PENDING
                driver = drivers[idx % len(drivers)]
            elif do.status == DeliveryStatus.YARD_STAGED:
                leg_status = LegStatus.COMPLETED
                driver = drivers[idx % len(drivers)]
            elif do.status == DeliveryStatus.FINAL_DELIVERY and step in (DeliveryStatus.YARD_STAGED, DeliveryStatus.FINAL_DELIVERY):
                leg_status = LegStatus.COMPLETED if step == DeliveryStatus.YARD_STAGED else LegStatus.IN_TRANSIT
                driver = drivers[idx % len(drivers)]
            elif do.status in (DeliveryStatus.EMPTY_STAGED, DeliveryStatus.COMPLETED):
                leg_status = LegStatus.COMPLETED
                driver = drivers[idx % len(drivers)]
            else:
                leg_status = LegStatus.PENDING
                driver = None

            now = now_utc()
            started = now - timedelta(hours=4) if leg_status != LegStatus.PENDING else None
            arrived = now - timedelta(hours=2) if leg_status == LegStatus.COMPLETED else None
            completed = now - timedelta(hours=1) if leg_status == LegStatus.COMPLETED else None

            leg = LegModel(
                team_id=team.id,
                delivery_order_id=do.id,
                step=step,
                move_type=move_type,
                service_type=service_type,
                status=leg_status,
                driver_id=driver.id if driver else None,
                pickup_location_id=pickup.id if pickup else None,
                pickup_date=days(-1 + idx),
                delivery_location_id=delivery.id if delivery else None,
                delivery_date=days(idx),
                started_at=started,
                arrived_at=arrived,
                completed_at=completed,
                storage_days=(idx),
            )
            db.add(leg)
            await db.flush()
            out.append(leg)

    print(f"[leg] {len(out)}")
    return out


async def seed_settlements(
    db, team: TeamModel, legs: list[LegModel],
) -> list[SettlementModel]:
    out = []
    completed_legs = [l for l in legs if l.status == LegStatus.COMPLETED]
    # 일부에만 settlement 생성 (12개)
    for i, leg in enumerate(completed_legs[:12]):
        existing = (await db.execute(
            select(SettlementModel).where(
                SettlementModel.team_id == team.id,
                SettlementModel.leg_id == leg.id,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue

        system_total = Decimal("250.00") + Decimal(str(50 * (i % 5)))
        # 상태 분포
        if i < 4:
            status = SettlementStatus.CALCULATED
            driver_reported = None
            discrepancy = None
            final_amount = None
            has_flag = False
        elif i < 8:
            status = SettlementStatus.ADJUSTED
            driver_reported = system_total + Decimal("50.00")
            discrepancy = driver_reported - system_total
            final_amount = None
            has_flag = True
        else:
            status = SettlementStatus.APPROVED
            driver_reported = system_total + Decimal("30.00") if i % 2 == 0 else system_total
            discrepancy = (driver_reported - system_total) if driver_reported else Decimal("0")
            final_amount = driver_reported or system_total
            has_flag = False

        s = SettlementModel(
            team_id=team.id,
            leg_id=leg.id,
            settlement_status=status,
            system_total=system_total,
            driver_reported_amount=driver_reported,
            discrepancy=discrepancy,
            has_flag=has_flag,
            final_amount=final_amount,
            is_settled=(status == SettlementStatus.APPROVED),
            approved_at=now_utc() if status == SettlementStatus.APPROVED else None,
        )
        db.add(s)
        await db.flush()
        out.append(s)

    print(f"[settlement] {len(out)}")
    return out


async def seed_notifications(
    db, team: TeamModel, test_user: UserModel,
    delivery_orders: list[DeliveryOrderModel],
) -> int:
    # 이미 있으면 skip — title 로 중복 검사
    existing_count = (await db.execute(
        select(NotificationModel).where(
            NotificationModel.team_id == team.id,
            NotificationModel.user_id == test_user.id,
        )
    )).scalars().all()
    if existing_count:
        print(f"[notification] skip ({len(existing_count)} 이미 존재)")
        return len(existing_count)

    samples = [
        ("DO_CREATED", "신규 D/O 등록", "신규 배송지시서가 추가되었습니다."),
        ("LEG_ASSIGNED", "Leg 배정 완료", "Leg #34 가 Carlos Mendoza 에게 배정되었습니다."),
        ("LEG_COMPLETED", "Leg 운송 완료", "MSCU2000005 Leg 가 완료되었습니다."),
        ("SETTLEMENT_FLAGGED", "정산 차이 감지", "Leg #21 정산 — 기사 보고와 시스템 차이 $50"),
        ("CONTAINER_DEMURRAGE", "체화료 임박", "MSCU2000003 LFD 가 2일 남았습니다."),
        ("DRIVER_OFFLINE", "기사 오프라인", "James Park 의 GPS 가 1시간 동안 끊겼습니다."),
        ("D/O_OVERDUE", "D/O 지연", "REF-2026-007 의 픽업 약속을 초과했습니다."),
        ("APPROVAL_NEEDED", "정산 승인 대기", "정산 #12 가 승인을 기다립니다."),
        ("SYSTEM_INFO", "시스템 알림", "야간 정산 배치가 완료되었습니다."),
        ("DRIVER_INVITED", "기사 초대 수락", "Roberto Silva 가 초대를 수락했습니다."),
        ("DOCUMENT_UPLOADED", "POD 업로드", "Leg #5 의 인수증이 업로드되었습니다."),
        ("API_KEY_USED", "API key 첫 사용", "외부 시스템이 API 키를 처음 사용했습니다."),
        ("STREET_TURN_MATCH", "Street Turn 매칭", "IMPORT REF-007 ↔ EXPORT REF-014 자동 매칭되었습니다."),
        ("CUSTOMER_CREATED", "신규 고객사", "Liberty Forwarders 가 등록되었습니다."),
        ("DRIVER_PASSWORD_RESET", "기사 비번 리셋", "Tom Anderson 의 비밀번호가 재설정되었습니다."),
    ]

    count = 0
    for i, (event, title, body) in enumerate(samples):
        is_read = (i >= 8)
        n = NotificationModel(
            team_id=team.id, user_id=test_user.id,
            channel=NotificationChannel.PUSH,
            status=NotificationStatus.SENT,
            event_type=event, title=title, body=body,
            is_read=is_read,
            read_at=now_utc() if is_read else None,
            sent_at=now_utc() - timedelta(hours=i),
        )
        db.add(n)
        count += 1

    await db.flush()
    print(f"[notification] {count}")
    return count


async def seed_api_keys(db, team: TeamModel, test_user: UserModel) -> int:
    samples = [
        ("Demo Integration — Slack", "Slack alert webhook 용 API 키"),
        ("Demo Integration — Zapier", "Zapier zaps 용"),
        ("Demo Read-only — Reporting", "외부 BI 도구 read-only 키"),
    ]
    count = 0
    for name, desc in samples:
        existing = (await db.execute(
            select(ApiKeyModel).where(
                ApiKeyModel.team_id == team.id,
                ApiKeyModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            continue
        token = secrets.token_urlsafe(32)
        full_key = f"tms_{token}"
        prefix = full_key[:12]
        k = ApiKeyModel(
            team_id=team.id, name=name, description=desc,
            key=full_key, prefix=prefix,
            expires_at=now_utc() + timedelta(days=90),
            created_by_user_id=test_user.id,
        )
        db.add(k)
        await db.flush()
        count += 1
    print(f"[api_key] {count}")
    return count


# ──────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────

async def main() -> None:
    Session = async_sessionmaker(write_engine, expire_on_commit=False)
    async with Session() as db:
        team = await get_team(db)
        print(f"=== team: {team.name} (id={team.id}) ===")

        test_user = (await db.execute(
            select(UserModel).where(UserModel.email == "test@test.com")
        )).scalar_one_or_none()
        if not test_user:
            print("[err] test@test.com 없음. seed_local.py 먼저 실행")
            sys.exit(1)

        customers = await seed_customers(db, team)
        terminals = await seed_terminals(db, team)
        vessels = await seed_vessels(db, team)
        locations = await seed_locations(db, team, customers)
        drivers = await seed_drivers(db, team)
        await seed_rate_settings(db, team)

        delivery_orders = await seed_delivery_orders(db, team, customers, terminals, vessels, locations)
        legs = await seed_legs(db, team, delivery_orders, drivers, locations)
        await seed_settlements(db, team, legs)
        await seed_notifications(db, team, test_user, delivery_orders)
        await seed_api_keys(db, team, test_user)

        await db.commit()

    print("\n=== Demo seed 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())
