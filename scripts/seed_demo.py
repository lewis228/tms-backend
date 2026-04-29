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
from charge_code.model import ChargeCodeModel
from charge_code.const.status import ChargeKind, ChargeUnit
from rate_card.model import RateCardModel
from delivery_order.model import DeliveryOrderModel
from delivery_order.const.status import DeliveryStatus, ShipmentDirection
from container.model import ContainerModel, ContainerEventModel
from container.const.status import ContainerSize, ContainerEventKind
from leg.model import LegModel
from leg.const.status import LegStatus, MoveType, ServiceType
from street_turn.model import StreetTurnModel
from street_turn.const.status import StreetTurnStatus
from street_turn.const.link_type import StreetTurnLinkType
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

# H-5: kind 분류 추가. 8 CUSTOMER + 3 CARRIER + 1 BROKER = 12.
# 튜플: (name, code, addr, contact_name, email, kind)
CUSTOMERS = [
    ("Acme Logistics", "ACME", "1100 Trade St, Long Beach CA 90802", "Sarah Kim", "sarah@acme.example", "CUSTOMER"),
    ("Pacific Imports", "PAC", "2400 Ocean Blvd, San Pedro CA 90731", "John Lee", "john@pacific.example", "CUSTOMER"),
    ("Bluewave Freight", "BLUE", "550 Wilmington Ave, Wilmington CA 90744", "Mike Chen", "mike@bluewave.example", "CUSTOMER"),
    ("Coastline Distribution", "COAST", "3200 Carson St, Carson CA 90745", "Anna Park", "anna@coastline.example", "CUSTOMER"),
    ("Global Trade Co", "GTC", "1500 Harbor Dr, Long Beach CA 90802", "Daniel Tan", "daniel@gtc.example", "CUSTOMER"),
    ("Sunrise Forwarding", "SUN", "780 Atlantic Ave, Long Beach CA 90802", "Rachel Park", "rachel@sunrise.example", "CUSTOMER"),
    ("Westport Logistics", "WEST", "440 Anaheim St, Wilmington CA 90744", "Brian Cho", "brian@westport.example", "CUSTOMER"),
    ("Anchor Shipping", "ANCH", "9000 Alameda St, Los Angeles CA 90002", "Christopher Yu", "chris@anchor.example", "CUSTOMER"),
    ("Harbor Light Trading", "HLT", "1200 Marine Way, Wilmington CA 90744", "Helen Jang", "helen@hltrade.example", "BROKER"),
    ("Pacific Crest Cargo", "PCC", "5600 Pier B St, Long Beach CA 90802", "Sam Park", "sam@pcc.example", "CARRIER"),
    ("Cascade Carriers Inc", "CCI", "2200 Avalon Blvd, Wilmington CA 90744", "Jenny Lim", "jenny@cascade.example", "CARRIER"),
    ("Liberty Forwarders", "LIB", "1800 Henry Ford Ave, Wilmington CA 90744", "Ethan Han", "ethan@liberty.example", "CARRIER"),
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

CHARGE_CODES: list[tuple[str, str, ChargeKind, ChargeUnit, Decimal | None, bool, bool, str]] = [
    # (code, name, kind, default_unit, default_amount, billable, payable, description)
    ("BASE_LINEHAUL",    "기본 운임 (Linehaul)",     ChargeKind.BASE,        ChargeUnit.FLAT,    Decimal("250.00"), True,  True,  "표준 drayage 기본 운임"),
    ("BOBTAIL",          "Bobtail 회차료",            ChargeKind.BASE,        ChargeUnit.FLAT,    Decimal("20.00"),  True,  True,  "트럭만 (컨X) 이동"),
    ("DRY_RUN",          "Dry Run (빠꾸)",            ChargeKind.PENALTY,     ChargeUnit.FLAT,    Decimal("85.00"),  True,  True,  "현장 도착했으나 작업 불가로 회차"),
    ("WAIT_PER_MIN",     "대기료 (분당)",             ChargeKind.ACCESSORIAL, ChargeUnit.MINUTE,  Decimal("1.50"),   True,  True,  "기사 대기 시간 분당 정산"),
    ("CHASSIS_PER_DIEM", "Chassis Per-Diem",          ChargeKind.ACCESSORIAL, ChargeUnit.DAY,     Decimal("35.00"),  True,  False, "챠시 일별 사용료 (풀 사용 시)"),
    ("CHASSIS_SPLIT",    "Chassis Split Fee",         ChargeKind.ACCESSORIAL, ChargeUnit.FLAT,    Decimal("55.00"),  True,  False, "챠시 별도 픽업/반납 비용"),
    ("FUEL_SURCHARGE",   "연료 Surcharge (%)",        ChargeKind.FUEL,        ChargeUnit.PERCENT, Decimal("12.00"),  True,  False, "기본 운임의 12% 연료 surcharge"),
    ("DEMURRAGE",        "Demurrage (체화료)",        ChargeKind.PENALTY,     ChargeUnit.DAY,     Decimal("150.00"), True,  False, "터미널 LFD 초과 시 일별"),
    ("DETENTION",        "Detention (반납 지연)",     ChargeKind.PENALTY,     ChargeUnit.DAY,     Decimal("125.00"), True,  False, "빈 컨 반납 지연 시 일별"),
    ("PIER_PASS",        "Pier Pass (TMF)",           ChargeKind.ACCESSORIAL, ChargeUnit.FLAT,    Decimal("36.71"),  True,  False, "LA/LB Pier Pass / TMF"),
    ("SCALE",            "Scale (계량)",              ChargeKind.ACCESSORIAL, ChargeUnit.FLAT,    Decimal("15.00"),  True,  False, "계량소 비용"),
    ("TOLL",             "Toll (통행료)",             ChargeKind.ACCESSORIAL, ChargeUnit.FLAT,    Decimal("12.00"),  True,  True,  "유료 도로 통행료"),
    ("PARTIAL_PAY",      "부분 지급",                 ChargeKind.DISCOUNT,    ChargeUnit.FLAT,    Decimal("0.00"),   False, True,  "터미널 휴장 등 사유로 부분 지급"),
    ("VAT_10",           "부가세 10%",                ChargeKind.TAX,         ChargeUnit.PERCENT, Decimal("10.00"),  True,  False, "한국 부가세 10%"),
    ("OTHER",            "기타 비용",                 ChargeKind.ACCESSORIAL, ChargeUnit.FLAT,    None,              True,  True,  "코드화 안 된 비용 — 메모로 구분"),
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
    from customer.const.status import PartnerKind
    out = []
    for name, code, addr, contact, email, kind in CUSTOMERS:
        existing = (await db.execute(
            select(CustomerModel).where(
                CustomerModel.team_id == team.id,
                CustomerModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        kind_enum = PartnerKind(kind)
        carrier_extras = {}
        if kind_enum == PartnerKind.CARRIER:
            carrier_extras = {
                "mc_number": f"MC{700000 + random.randint(1000, 9999)}",
                "dot_number": f"DOT{1000000 + random.randint(10000, 99999)}",
                "payment_terms_days": 30,
            }
        c = CustomerModel(
            team_id=team.id, name=name, code=code,
            kind=kind_enum,
            billing_address=addr, contact_name=contact,
            contact_email=email,
            contact_phone=f"+1-562-555-{random.randint(1000, 9999)}",
            **carrier_extras,
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


async def seed_drivers(
    db, team: TeamModel,
    customers: list[CustomerModel] | None = None,
) -> list[DriverModel]:
    from driver.const.status import EmploymentKind, PaymentTermsKind
    out = []
    # 8 기사: 5 IN_HOUSE, 2 OWNER_OPERATOR_SOLO, 1 CARRIER_DRIVER
    employment_dist = [
        EmploymentKind.IN_HOUSE, EmploymentKind.IN_HOUSE,
        EmploymentKind.IN_HOUSE, EmploymentKind.IN_HOUSE, EmploymentKind.IN_HOUSE,
        EmploymentKind.OWNER_OPERATOR_SOLO, EmploymentKind.OWNER_OPERATOR_SOLO,
        EmploymentKind.CARRIER_DRIVER,
    ]
    carriers = [c for c in (customers or []) if c.kind.value == "CARRIER"]
    first_carrier_id = carriers[0].id if carriers else None
    for idx, (name, email, phone, license_no, state, truck) in enumerate(DRIVERS):
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
        # truck 은 이제 별도 테이블 (H-3). seed_trucks 가 처리.
        _ = truck  # noqa: F841 — DRIVERS 튜플의 마지막 요소 (legacy)
        emp = employment_dist[idx % len(employment_dist)]
        carrier_id = first_carrier_id if emp == EmploymentKind.CARRIER_DRIVER else None
        terms_kind = (
            PaymentTermsKind.PERCENT_OF_REVENUE
            if emp == EmploymentKind.OWNER_OPERATOR_SOLO
            else (PaymentTermsKind.SALARY if emp == EmploymentKind.IN_HOUSE else PaymentTermsKind.PER_LEG)
        )
        terms_value = (
            Decimal("70.0000") if emp == EmploymentKind.OWNER_OPERATOR_SOLO
            else (Decimal("4500.00") if emp == EmploymentKind.IN_HOUSE else Decimal("250.00"))
        )
        d = DriverModel(
            team_id=team.id, user_id=user.id,
            license_number=license_no, license_state=state,
            employment_kind=emp,
            carrier_id=carrier_id,
            payment_terms_kind=terms_kind,
            payment_terms_value=terms_value,
        )
        db.add(d)
        await db.flush()
        out.append(d)
    print(f"[driver] {len(out)}")
    return out


async def seed_trucks(
    db, team: TeamModel, drivers: list[DriverModel],
) -> list:
    """회사 트럭 8대 + 외부기사(첫 5명) 본인 트럭 5대 = 13대."""
    from truck.model import TruckModel
    from truck.const.status import TruckOwnerKind, TruckStatus

    out = []
    company_trucks = [
        ("TX-COMP-101", "1HGCM82633A123456", "Freightliner", "Cascadia", 2022),
        ("TX-COMP-102", "1HGCM82633A123457", "Freightliner", "Cascadia", 2023),
        ("TX-COMP-103", "1HGCM82633A123458", "Volvo", "VNL 760", 2021),
        ("TX-COMP-104", "1HGCM82633A123459", "Kenworth", "T680", 2020),
        ("TX-COMP-105", "1HGCM82633A123460", "Peterbilt", "579", 2022),
        ("TX-COMP-106", "1HGCM82633A123461", "Mack", "Anthem", 2019),
        ("TX-COMP-107", "1HGCM82633A123462", "International", "LT", 2021),
        ("TX-COMP-108", "1HGCM82633A123463", "Volvo", "VNL 860", 2023),
    ]
    for plate, vin, make, model, year in company_trucks:
        existing = (await db.execute(
            select(TruckModel).where(
                TruckModel.team_id == team.id,
                TruckModel.plate_no == plate,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        tk = TruckModel(
            team_id=team.id, plate_no=plate, vin=vin,
            make=make, model=model, year=year,
            owner_kind=TruckOwnerKind.COMPANY,
            status=TruckStatus.ACTIVE,
        )
        db.add(tk)
        await db.flush()
        out.append(tk)

    # 외부기사 본인 트럭 5대
    for i, drv in enumerate(drivers[:5]):
        plate = f"TX-OO-{200 + i:03d}"
        existing = (await db.execute(
            select(TruckModel).where(
                TruckModel.team_id == team.id,
                TruckModel.plate_no == plate,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        tk = TruckModel(
            team_id=team.id, plate_no=plate,
            make="Freightliner", model="Cascadia", year=2018 + i,
            owner_kind=TruckOwnerKind.DRIVER,
            owner_driver_id=drv.id,
            status=TruckStatus.ACTIVE,
        )
        db.add(tk)
        await db.flush()
        out.append(tk)

    print(f"[truck] {len(out)}")
    return out


async def seed_equipment_pools(db, team: TeamModel) -> list:
    from equipment_pool.model import EquipmentPoolModel
    from equipment_pool.const.status import EquipmentPoolKind

    pools_data = [
        ("TRAC Intermodal", EquipmentPoolKind.THIRD_PARTY_POOL, "TRAC Intermodal LLC"),
        ("FlexiVan", EquipmentPoolKind.THIRD_PARTY_POOL, "FlexiVan Leasing"),
        ("DCLI", EquipmentPoolKind.THIRD_PARTY_POOL, "Direct ChassisLink Inc."),
        ("GCT-NJ Terminal Pool", EquipmentPoolKind.TERMINAL_POOL, "GCT NJ"),
    ]
    out = []
    for name, kind, operator in pools_data:
        existing = (await db.execute(
            select(EquipmentPoolModel).where(
                EquipmentPoolModel.team_id == team.id,
                EquipmentPoolModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        p = EquipmentPoolModel(
            team_id=team.id, name=name, kind=kind, operator=operator,
        )
        db.add(p)
        await db.flush()
        out.append(p)
    print(f"[equipment_pool] {len(out)}")
    return out


async def seed_chassis(
    db, team: TeamModel,
    drivers: list[DriverModel],
    pools: list,
) -> list:
    """30 chassis: 회사 8 + 기사 4 + 풀 18."""
    from chassis.model import ChassisModel
    from chassis.const.status import ChassisOwnerKind, ChassisSize, ChassisStatus

    out = []
    # 회사 8
    for i in range(8):
        plate = f"CCH-{2000 + i:05d}"
        existing = (await db.execute(
            select(ChassisModel).where(
                ChassisModel.team_id == team.id,
                ChassisModel.chassis_number == plate,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        ch = ChassisModel(
            team_id=team.id, chassis_number=plate,
            size=[ChassisSize.SIZE_20, ChassisSize.SIZE_40, ChassisSize.SIZE_45][i % 3],
            owner_kind=ChassisOwnerKind.COMPANY,
            status=ChassisStatus.AVAILABLE,
        )
        db.add(ch)
        await db.flush()
        out.append(ch)

    # 기사 4 (driver-owned)
    for i, drv in enumerate(drivers[:4]):
        plate = f"DCH-{i:03d}-{drv.id:04d}"
        existing = (await db.execute(
            select(ChassisModel).where(
                ChassisModel.team_id == team.id,
                ChassisModel.chassis_number == plate,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        ch = ChassisModel(
            team_id=team.id, chassis_number=plate,
            size=ChassisSize.SIZE_40,
            owner_kind=ChassisOwnerKind.DRIVER,
            owner_driver_id=drv.id,
            status=ChassisStatus.AVAILABLE,
        )
        db.add(ch)
        await db.flush()
        out.append(ch)

    # 풀 18 (각 풀별 4-5개)
    pool_prefixes = ["TRAC", "FLEX", "DCLI", "GCTN"]
    for pi, p in enumerate(pools):
        for k in range(5 if pi < 2 else 4):
            plate = f"{pool_prefixes[pi]}-{p.id:03d}-{k:03d}"
            existing = (await db.execute(
                select(ChassisModel).where(
                    ChassisModel.team_id == team.id,
                    ChassisModel.chassis_number == plate,
                )
            )).scalar_one_or_none()
            if existing:
                out.append(existing)
                continue
            ch = ChassisModel(
                team_id=team.id, chassis_number=plate,
                size=[ChassisSize.SIZE_20, ChassisSize.SIZE_40][(pi + k) % 2],
                owner_kind=(
                    ChassisOwnerKind.TERMINAL_POOL
                    if p.kind.value == "TERMINAL_POOL"
                    else ChassisOwnerKind.THIRD_PARTY_POOL
                ),
                owner_pool_id=p.id,
                status=ChassisStatus.AT_POOL,
            )
            db.add(ch)
            await db.flush()
            out.append(ch)

    print(f"[chassis] {len(out)}")
    return out


async def seed_charge_codes(db, team: TeamModel) -> list[ChargeCodeModel]:
    out: list[ChargeCodeModel] = []
    for code, name, kind, unit, amount, billable, payable, desc in CHARGE_CODES:
        existing = (await db.execute(
            select(ChargeCodeModel).where(
                ChargeCodeModel.team_id == team.id,
                ChargeCodeModel.code == code,
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        cc = ChargeCodeModel(
            team_id=team.id, code=code, name=name, kind=kind,
            default_unit=unit, default_amount=amount,
            is_billable_to_customer=billable, is_payable_to_driver=payable,
            description=desc,
        )
        db.add(cc)
        await db.flush()
        out.append(cc)
    print(f"[charge_code] {len(out)}")
    return out


async def seed_rate_cards(
    db, team: TeamModel,
    charge_codes: list[ChargeCodeModel],
    customers: list[CustomerModel],
    terminals: list[TerminalModel],
) -> list[RateCardModel]:
    """약 30 row — 데모 매트릭스. 우선순위 큰 게 specific."""
    today = date.today()
    by_code = {c.code: c for c in charge_codes}

    rules: list[dict] = []
    base = by_code["BASE_LINEHAUL"]
    bobtail = by_code["BOBTAIL"]
    dry_run = by_code["DRY_RUN"]
    wait = by_code["WAIT_PER_MIN"]
    chassis_per_diem = by_code["CHASSIS_PER_DIEM"]
    chassis_split = by_code["CHASSIS_SPLIT"]
    fuel = by_code["FUEL_SURCHARGE"]
    demurrage = by_code["DEMURRAGE"]
    detention = by_code["DETENTION"]
    pier_pass = by_code["PIER_PASS"]
    vat = by_code["VAT_10"]

    # 글로벌 default 룰 (priority 0)
    for cc in (base, bobtail, dry_run, wait, chassis_per_diem, chassis_split, demurrage, detention, pier_pass):
        rules.append(dict(
            charge_code_id=cc.id, name=f"Global {cc.code}", priority=0,
            unit=cc.default_unit, amount=cc.default_amount,
            effective_from=today - timedelta(days=30),
            description=f"Default rule for {cc.code}",
        ))
    # FUEL / VAT 은 percent
    rules.append(dict(
        charge_code_id=fuel.id, name="Global Fuel Surcharge", priority=0,
        unit=ChargeUnit.PERCENT, percent=Decimal("0.1200"),
        effective_from=today - timedelta(days=30),
    ))
    rules.append(dict(
        charge_code_id=vat.id, name="Global VAT 10%", priority=0,
        unit=ChargeUnit.PERCENT, percent=Decimal("0.1000"),
        effective_from=today - timedelta(days=30),
    ))

    # 사이즈별 BASE 차등 (priority 5)
    for size_name, amount in [
        ("SIZE_20GP", Decimal("220.00")),
        ("SIZE_40GP", Decimal("250.00")),
        ("SIZE_40HC", Decimal("260.00")),
        ("SIZE_40OT", Decimal("295.00")),
        ("SIZE_45HC", Decimal("310.00")),
        ("SIZE_20RF", Decimal("340.00")),
        ("SIZE_40RF", Decimal("370.00")),
    ]:
        rules.append(dict(
            charge_code_id=base.id, name=f"BASE {size_name}", priority=5,
            unit=ChargeUnit.FLAT, amount=amount, scope_size=size_name,
            effective_from=today - timedelta(days=30),
        ))

    # 고객사별 프리미엄 BASE (priority 10) — 상위 2개 customer
    for cust in customers[:2]:
        rules.append(dict(
            charge_code_id=base.id, name=f"Premium BASE for {cust.name}", priority=10,
            unit=ChargeUnit.FLAT, amount=Decimal("310.00"),
            scope_customer_id=cust.id,
            effective_from=today - timedelta(days=30),
        ))

    # 터미널별 PIER PASS adjust (priority 7) — 상위 3 터미널
    for term in terminals[:3]:
        rules.append(dict(
            charge_code_id=pier_pass.id, name=f"Pier Pass at {term.code}", priority=7,
            unit=ChargeUnit.FLAT, amount=Decimal("36.71"),
            scope_terminal_id=term.id,
            effective_from=today - timedelta(days=30),
        ))

    # 고객사+사이즈 매트릭스 (priority 15)
    if customers:
        rules.append(dict(
            charge_code_id=base.id,
            name=f"BASE 40HC for {customers[0].name}",
            priority=15, unit=ChargeUnit.FLAT, amount=Decimal("295.00"),
            scope_customer_id=customers[0].id, scope_size="SIZE_40HC",
            effective_from=today - timedelta(days=30),
        ))

    out: list[RateCardModel] = []
    for rule in rules:
        existing = (await db.execute(
            select(RateCardModel).where(
                RateCardModel.team_id == team.id,
                RateCardModel.name == rule["name"],
            )
        )).scalar_one_or_none()
        if existing:
            out.append(existing)
            continue
        rc = RateCardModel(team_id=team.id, **rule)
        db.add(rc)
        await db.flush()
        out.append(rc)
    print(f"[rate_card] {len(out)}")
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
) -> tuple[list[DeliveryOrderModel], list[ContainerModel]]:
    customer_locs = [l for l in locations if l.kind == LocationKind.CUSTOMER]
    yards = [l for l in locations if l.kind == LocationKind.YARD]

    do_out: list[DeliveryOrderModel] = []
    container_out: list[ContainerModel] = []
    NUM_DO = 24

    # 컨테이너 분포: D/O 17개 1컨, 6개 2컨, 1개 3컨 → 총 31. 평균 1.29
    # H-1 plan 의 평균 1.7 에 가깝도록 살짝 강화: 14×1, 8×2, 2×3 = 36 (avg 1.5).
    DO_CONTAINER_COUNT = (
        [1] * 14 + [2] * 8 + [3] * 2
    )
    random.seed(42)
    random.shuffle(DO_CONTAINER_COUNT)

    for i in range(NUM_DO):
        bl = f"MSCU{1000000 + i:07d}"
        existing = (await db.execute(
            select(DeliveryOrderModel).where(
                DeliveryOrderModel.team_id == team.id,
                DeliveryOrderModel.bl_number == bl,
            )
        )).scalar_one_or_none()
        if existing:
            do_out.append(existing)
            existing_containers = (await db.execute(
                select(ContainerModel).where(
                    ContainerModel.team_id == team.id,
                    ContainerModel.delivery_order_id == existing.id,
                )
            )).scalars().all()
            container_out.extend(existing_containers)
            continue

        cust = customers[i % len(customers)]
        term = terminals[i % len(terminals)]
        vess = vessels[i % len(vessels)]

        # 진행 단계 분포 — 다양한 상태로
        if i < 4:
            status = DeliveryStatus.PLANNING
        elif i < 8:
            status = DeliveryStatus.DISPATCHED
        elif i < 12:
            status = DeliveryStatus.YARD_STAGED
        elif i < 16:
            status = DeliveryStatus.FINAL_DELIVERY
        elif i < 20:
            status = DeliveryStatus.EMPTY_STAGED
        else:
            status = DeliveryStatus.COMPLETED

        direction = ShipmentDirection.IMPORT if i % 3 != 0 else ShipmentDirection.EXPORT

        do = DeliveryOrderModel(
            team_id=team.id,
            status=status, direction=direction,
            bl_number=bl, booking_number=f"BKG{500000 + i:06d}",
            reference=f"REF-2026-{i + 1:03d}",
            customer_id=cust.id,
            terminal_id=term.id,
            vessel_id=vess.id,
            eta=days(-3 + i % 10),
            bl_released=(i % 2 == 0),
            internal_note=None,
        )
        db.add(do)
        await db.flush()
        do_out.append(do)

        # 컨테이너 N개 생성
        n_containers = DO_CONTAINER_COUNT[i] if i < len(DO_CONTAINER_COUNT) else 1
        for seq in range(1, n_containers + 1):
            # 컨테이너별로 다른 도착지/사이즈 가능
            delivery_loc = customer_locs[(i + seq) % len(customer_locs)]
            return_loc = yards[(i + seq) % len(yards)]
            size = CONTAINER_SIZES[(i + seq) % len(CONTAINER_SIZES)]
            container_no = (
                None if status == DeliveryStatus.PLANNING
                else f"MSCU{2000000 + i * 10 + seq:07d}"
            )
            c_status = status  # D/O 와 동일 status 로 시작

            c = ContainerModel(
                team_id=team.id,
                delivery_order_id=do.id,
                sequence_no=seq,
                container_number=container_no,
                seal_no=f"SEAL{300000 + i * 10 + seq:06d}",
                size=size,
                type="DRY" if size not in (ContainerSize.SIZE_20RF, ContainerSize.SIZE_40RF) else "RF",
                weight_kg=Decimal(str(15000 + (i * 137 + seq * 211) % 8000)),
                # H-4: chassis 마스터로 분리. seed_chassis_links 가 일부 컨에 chassis_id 매핑.
                pickup_appointment=days(i % 7),
                delivery_appointment=days(1 + (i + seq) % 5),
                return_appointment=days(3 + (i + seq) % 5),
                demurrage_lfd=(date.today() + timedelta(days=2 + (i + seq) % 5)),
                detention_lfd=(date.today() + timedelta(days=5 + (i + seq) % 5)),
                empty_date=days(2 + (i + seq) % 4) if status in (DeliveryStatus.EMPTY_STAGED, DeliveryStatus.COMPLETED) else None,
                loaded_date=days(-1 + (i + seq) % 3) if direction == ShipmentDirection.EXPORT else None,
                delivery_location_id=delivery_loc.id,
                return_location_id=return_loc.id,
                service_type=ServiceType.LIVE if (i + seq) % 2 == 0 else ServiceType.DROP,
                pier_pass_paid=(i % 3 == 0),
                customs_cleared=(i % 4 == 0),
                status=c_status,
            )
            db.add(c)
            await db.flush()
            container_out.append(c)

    print(f"[delivery_order] {len(do_out)} / [container] {len(container_out)}")
    return do_out, container_out


async def seed_legs(
    db, team: TeamModel,
    delivery_orders: list[DeliveryOrderModel],
    containers: list[ContainerModel],
    drivers: list[DriverModel],
    locations: list[LocationModel],
) -> list[LegModel]:
    out = []
    customer_locs = [l for l in locations if l.kind == LocationKind.CUSTOMER]
    yards = [l for l in locations if l.kind == LocationKind.YARD]
    ports = [l for l in locations if l.kind == LocationKind.PORT]

    # do_id → containers 매핑 (sequence_no 정렬)
    do_to_containers: dict[int, list[ContainerModel]] = {}
    for c in containers:
        do_to_containers.setdefault(c.delivery_order_id, []).append(c)
    for cs in do_to_containers.values():
        cs.sort(key=lambda c: c.sequence_no)

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

            # container_id 매핑 — D/O 의 첫 컨테이너 (멀티 컨이면 첫 번째)
            do_containers = do_to_containers.get(do.id, [])
            container_id = do_containers[0].id if do_containers else None

            # H-6: leg_kind 매핑 (step + move_type 기반)
            from leg.const.status import LegKind
            if move_type == MoveType.EMPTY:
                kind = LegKind.RETURN if step == DeliveryStatus.EMPTY_STAGED else LegKind.REPOSITION
            elif step == DeliveryStatus.YARD_STAGED:
                kind = LegKind.PICKUP
            elif step == DeliveryStatus.FINAL_DELIVERY:
                kind = LegKind.LIVE_UNLOAD if service_type == ServiceType.LIVE else LegKind.DROP
            else:
                kind = LegKind.PICKUP

            leg = LegModel(
                team_id=team.id,
                delivery_order_id=do.id,
                container_id=container_id,
                container_at_start_id=container_id,
                container_at_end_id=container_id,
                step=step,
                move_type=move_type,
                service_type=service_type,
                leg_kind=kind,
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

            # H-6: 첫 leg 에 leg_stop 2개 시드 (PICKUP_FULL → DROP_FULL)
            if idx == 0 and pickup and delivery and move_type != MoveType.EMPTY:
                from leg_stop.model import LegStopModel
                from leg.const.status import StopKind
                db.add(LegStopModel(
                    team_id=team.id, leg_id=leg.id, sequence_no=1,
                    stop_kind=StopKind.PICKUP_FULL,
                    location_id=pickup.id, container_id=container_id,
                    arrived_at=started, departed_at=arrived,
                ))
                db.add(LegStopModel(
                    team_id=team.id, leg_id=leg.id, sequence_no=2,
                    stop_kind=StopKind.DROP_FULL,
                    location_id=delivery.id, container_id=container_id,
                    arrived_at=arrived, departed_at=completed,
                ))
                await db.flush()

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
# Street Turn (H-8)
# ──────────────────────────────────────────────────────────────────────────

async def seed_street_turns(
    db, team: TeamModel,
    delivery_orders: list[DeliveryOrderModel],
    containers: list[ContainerModel],
    test_user: UserModel,
) -> list[StreetTurnModel]:
    """
    Street turn 4건 생성 (REQUESTED 2 / APPROVED 1 / REJECTED 1).
    - import_order_id, export_order_id 는 unique → DO 4쌍 = 8개의 서로 다른 DO 사용
    - 일부는 container_id 로 정규화된 컨테이너 연결, 일부는 container_number 만 보유
    """
    # 이미 시드된 게 있으면 스킵 (idempotent)
    existing = (await db.execute(
        select(StreetTurnModel).where(StreetTurnModel.team_id == team.id)
    )).scalars().all()
    if existing:
        print(f"[street_turn] {len(existing)} already seeded; skip")
        return list(existing)

    if len(delivery_orders) < 8:
        print("[street_turn] DO < 8; skip")
        return []

    # IMPORT 방향 D/O 4개와 EXPORT 방향 D/O 4개를 짝짓는다.
    import_dos = [d for d in delivery_orders if d.direction == ShipmentDirection.IMPORT][:4]
    export_dos = [d for d in delivery_orders if d.direction == ShipmentDirection.EXPORT][:4]
    if len(import_dos) < 4 or len(export_dos) < 4:
        # IMPORT/EXPORT 가 모자라면 그냥 앞 8개를 절반씩 사용 (idempotent fallback)
        import_dos = delivery_orders[:4]
        export_dos = delivery_orders[4:8]

    pairs = list(zip(import_dos, export_dos))

    # IMPORT D/O 의 첫 컨테이너를 가져와 street_turn 의 container_id 로 사용
    def first_container_for(do_id: int) -> ContainerModel | None:
        for c in containers:
            if c.delivery_order_id == do_id:
                return c
        return None

    out: list[StreetTurnModel] = []
    now = now_utc()

    # 1) REQUESTED — container_id 보유
    imp, exp = pairs[0]
    cnt = first_container_for(imp.id)
    out.append(StreetTurnModel(
        team_id=team.id,
        import_order_id=imp.id,
        export_order_id=exp.id,
        container_id=cnt.id if cnt else None,
        container_number=cnt.container_number if cnt else "MSCU0000001",
        link_type=StreetTurnLinkType.MANUAL,
        status=StreetTurnStatus.REQUESTED,
        requested_by=test_user.id,
        requested_at=now - timedelta(hours=4),
        created_by_user_id=test_user.id,
    ))

    # 2) REQUESTED — container_id 없음 (string 만)
    imp, exp = pairs[1]
    out.append(StreetTurnModel(
        team_id=team.id,
        import_order_id=imp.id,
        export_order_id=exp.id,
        container_number="MSCU0000002",
        link_type=StreetTurnLinkType.AUTO,
        status=StreetTurnStatus.REQUESTED,
        requested_by=test_user.id,
        requested_at=now - timedelta(hours=2),
        created_by_user_id=test_user.id,
    ))

    # 3) APPROVED — container_event(STREET_TURNED) 자동기록 케이스
    imp, exp = pairs[2]
    cnt = first_container_for(imp.id)
    approved_at = now - timedelta(minutes=30)
    st_approved = StreetTurnModel(
        team_id=team.id,
        import_order_id=imp.id,
        export_order_id=exp.id,
        container_id=cnt.id if cnt else None,
        container_number=cnt.container_number if cnt else "MSCU0000003",
        link_type=StreetTurnLinkType.MANUAL,
        status=StreetTurnStatus.APPROVED,
        carrier_approval_no="MSC-ST-2026-0042",
        requested_by=test_user.id,
        requested_at=now - timedelta(hours=8),
        approved_by=test_user.id,
        approved_at=approved_at,
        created_by_user_id=test_user.id,
    )
    out.append(st_approved)
    if cnt:
        out_event = ContainerEventModel(
            team_id=team.id,
            container_id=cnt.id,
            event_kind=ContainerEventKind.STREET_TURNED,
            occurred_at=approved_at,
            note="Street turn approved (carrier_approval_no=MSC-ST-2026-0042)",
            created_by_user_id=test_user.id,
        )
        db.add(out_event)

    # 4) REJECTED
    imp, exp = pairs[3]
    out.append(StreetTurnModel(
        team_id=team.id,
        import_order_id=imp.id,
        export_order_id=exp.id,
        container_number="MSCU0000004",
        link_type=StreetTurnLinkType.MANUAL,
        status=StreetTurnStatus.REJECTED,
        requested_by=test_user.id,
        requested_at=now - timedelta(hours=10),
        rejected_reason="Container size mismatch",
        created_by_user_id=test_user.id,
    ))

    for st in out:
        db.add(st)
    await db.flush()
    print(f"[street_turn] {len(out)} seeded (2 REQUESTED, 1 APPROVED, 1 REJECTED)")
    return out


# ──────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────

async def seed_v3_team_settings(db, team: TeamModel) -> None:
    """v3: 거리 단위 라벨 / 통화 / distance provider 설정."""
    changed = False
    if team.distance_unit_label is None:
        team.distance_unit_label = "km"
        changed = True
    if team.currency_label is None:
        team.currency_label = "KRW"
        changed = True
    if team.currency_symbol is None:
        team.currency_symbol = "₩"
        changed = True
    if team.distance_provider is None:
        team.distance_provider = "MANUAL"
        changed = True
    if changed:
        await db.flush()
    print(f"[v3 team] settings={team.distance_unit_label}/{team.currency_label}/{team.distance_provider}")


_V3_CHARGE_CODES = [
    # (code, name, kind, default_unit, default_amount, unit_label, category, signed, payee, payer)
    ("WAITING_10MIN",        "대기 (10분당)",      "ACCESSORIAL", "MINUTE", Decimal("10000"), "10분",  "WAITING",    False, "DRIVER",   None),
    ("WAITING_FLAT_30",      "대기 (30분 정액)",   "ACCESSORIAL", "FLAT",   Decimal("30000"), "건",    "WAITING",    False, "DRIVER",   None),
    ("EXTRA_STOP",           "추가 정차",          "ACCESSORIAL", "FLAT",   Decimal("50000"), "건",    "EXTRA_STOP", False, "DRIVER",   None),
    ("DRY_RUN_FEE",          "빠꾸 보상",          "ACCESSORIAL", "FLAT",   Decimal("100000"),"건",    "DRY_RUN",    False, "DRIVER",   None),
    ("CHASSIS_RENTAL_DELAY", "섀시 대여 지체",     "ACCESSORIAL", "FLAT",   Decimal("30000"), "건",    "EXTRA_STOP", False, "DRIVER",   None),
    ("TERMINAL_CLOSED_FEE",  "터미널 closed 보상", "ACCESSORIAL", "FLAT",   Decimal("50000"), "건",    "DRY_RUN",    False, "DRIVER",   None),
    ("DRIVER_FAULT_PENALTY", "기사 과실 페널티",   "PENALTY",     "FLAT",   Decimal("-50000"),"건",    "PENALTY",    True,  "DRIVER",   None),
    ("FUEL_SURCHARGE_PCT",   "유류할증 (%)",       "FUEL",        "PERCENT",Decimal("5"),     "%",     "SURCHARGE",  False, None,       "CUSTOMER"),
    ("BASE_PORTION_SPLIT",   "기본운임 분배",      "ACCESSORIAL", "FLAT",   Decimal("0"),     "건",    "ADJUSTMENT", True,  "DRIVER",   None),
    # B.10 Demurrage / Detention 자동 카운터가 사용하는 코드. 매일 1건 자동 LegCharge 적용.
    ("DEMURRAGE_PER_DAY",    "Demurrage (일일)",   "PENALTY",     "DAY",    Decimal("80000"), "일",    "PENALTY",    False, None,       "CUSTOMER"),
    ("DETENTION_PER_DAY",    "Detention (일일)",   "PENALTY",     "DAY",    Decimal("100000"),"일",    "PENALTY",    False, None,       "CUSTOMER"),
]


async def seed_v3_charge_codes(db, team: TeamModel) -> dict[str, ChargeCodeModel]:
    """v3 변동분 ChargeCode 추가 + 보강 (unit_label/category/signed/payee_default)."""
    from charge_code.const.status import ChargeKind, ChargeUnit, ChargeCategory, PartyKind
    out: dict[str, ChargeCodeModel] = {}
    for (code, name, kind, unit, amt, unit_label, cat, signed, payee, payer) in _V3_CHARGE_CODES:
        existing = (await db.execute(
            select(ChargeCodeModel).where(
                ChargeCodeModel.team_id == team.id,
                ChargeCodeModel.code == code,
            )
        )).scalar_one_or_none()
        if existing:
            existing.unit_label = unit_label
            existing.category = ChargeCategory(cat)
            existing.signed = signed
            existing.payee_default = PartyKind(payee) if payee else None
            existing.payer_default = PartyKind(payer) if payer else None
            out[code] = existing
            continue
        cc = ChargeCodeModel(
            team_id=team.id,
            code=code, name=name,
            kind=ChargeKind(kind),
            default_unit=ChargeUnit(unit),
            default_amount=amt,
            unit_label=unit_label,
            category=ChargeCategory(cat),
            signed=signed,
            payee_default=PartyKind(payee) if payee else None,
            payer_default=PartyKind(payer) if payer else None,
            is_billable_to_customer=(payer == "CUSTOMER"),
            is_payable_to_driver=(payee == "DRIVER"),
        )
        db.add(cc)
        await db.flush()
        out[code] = cc
    print(f"[v3 charge_code] {len(out)}")
    return out


async def seed_v3_distance_matrix(
    db, team: TeamModel, locations: list[LocationModel],
) -> int:
    """v3 location pair 거리 캐시 — 좌표 기반 haversine 거리 시드 (수동값)."""
    from distance_matrix.model import DistanceMatrixModel
    import math
    def haversine(a, b) -> float:
        if not (a.latitude and a.longitude and b.latitude and b.longitude):
            return 0.0
        la1, lo1, la2, lo2 = map(math.radians, [float(a.latitude), float(a.longitude), float(b.latitude), float(b.longitude)])
        dla, dlo = la2 - la1, lo2 - lo1
        h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
        return 2 * 6371.0 * math.asin(math.sqrt(h))

    count = 0
    for o in locations:
        for d in locations:
            if o.id == d.id:
                continue
            existing = (await db.execute(
                select(DistanceMatrixModel).where(
                    DistanceMatrixModel.team_id == team.id,
                    DistanceMatrixModel.origin_location_id == o.id,
                    DistanceMatrixModel.destination_location_id == d.id,
                )
            )).scalar_one_or_none()
            if existing:
                continue
            km = haversine(o, d)
            if km <= 0:
                continue
            # 평균 50km/h 가정 → 분
            duration = (km / 50.0) * 60.0
            db.add(DistanceMatrixModel(
                team_id=team.id,
                origin_location_id=o.id,
                destination_location_id=d.id,
                distance_value=Decimal(f"{km:.4f}"),
                duration_min=Decimal(f"{duration:.4f}"),
                source="MANUAL",
                measured_at=now_utc(),
            ))
            count += 1
    if count:
        await db.flush()
    print(f"[v3 distance_matrix] {count}")
    return count


async def seed_v3_rate_tariffs(db, team: TeamModel) -> int:
    """v3 거리×단가룰 마스터 — 4가지 move_type."""
    from rate_tariff.model import RateTariffModel
    rules = [
        ("기본 2026Q2 / FULL_LOADED",  "FULL_LOADED",  Decimal("1200"), Decimal("50"), Decimal("50000")),
        ("기본 2026Q2 / EMPTY_LOADED", "EMPTY_LOADED", Decimal("900"),  Decimal("30"), Decimal("30000")),
        ("기본 2026Q2 / TRUCK_ONLY",   "TRUCK_ONLY",   Decimal("600"),  Decimal("0"),  Decimal("0")),
        ("기본 2026Q2 / CHASSIS_ONLY", "CHASSIS_ONLY", Decimal("700"),  Decimal("0"),  Decimal("10000")),
    ]
    count = 0
    for (name, move, per_value, per_min, flat) in rules:
        existing = (await db.execute(
            select(RateTariffModel).where(
                RateTariffModel.team_id == team.id,
                RateTariffModel.name == name,
            )
        )).scalar_one_or_none()
        if existing:
            continue
        db.add(RateTariffModel(
            team_id=team.id,
            name=name,
            move_type=move,
            per_value=per_value,
            per_min=per_min,
            flat_base=flat,
            effective_from=date(2026, 4, 1),
            priority=10,
        ))
        count += 1
    if count:
        await db.flush()
    print(f"[v3 rate_tariff] {count}")
    return count


async def seed_v3_legs_full(
    db, team: TeamModel,
    legs: list[LegModel],
    locations: list[LocationModel],
) -> None:
    """v3 leg에 대한 backfill:
      - move_type_v3 (기존 enum 매핑)
      - container_stop 시퀀스 + Leg.from_stop_id/to_stop_id 백필
      - leg_driver_segment 1개 (기존 driver_id 기반)
      - leg_rate snapshot (RateTariff lookup → distance × per_value 계산)
      - 일부 leg에 추가 LegCharge (시나리오 검증)
    """
    from container_stop.model import ContainerStopModel
    from leg_driver_segment.model import LegDriverSegmentModel
    from leg_rate.model import LegRateModel
    from rate_tariff.model import RateTariffModel
    from distance_matrix.model import DistanceMatrixModel
    from leg_charge.model import LegChargeModel
    from leg.const.status import StopRole, MoveTypeV3, LegRateSource, HandoverReason

    # move_type → MoveTypeV3 매핑
    move_map = {"LOADED": "FULL_LOADED", "EMPTY": "EMPTY_LOADED", "BOBTAIL": "TRUCK_ONLY"}

    # tariff lookup (move_type → tariff)
    tariffs = (await db.execute(
        select(RateTariffModel).where(RateTariffModel.team_id == team.id)
    )).scalars().all()
    tariff_by_move: dict[str, RateTariffModel] = {}
    for t in tariffs:
        if t.move_type:
            tariff_by_move[str(t.move_type.value if hasattr(t.move_type, "value") else t.move_type)] = t

    # ChargeCode lookup (시나리오 LegCharge용)
    cc_rows = (await db.execute(
        select(ChargeCodeModel).where(
            ChargeCodeModel.team_id == team.id,
            ChargeCodeModel.code.in_([
                "WAITING_10MIN", "TERMINAL_CLOSED_FEE", "DRIVER_FAULT_PENALTY",
            ]),
        )
    )).scalars().all()
    cc_by_code = {c.code: c for c in cc_rows}

    # Container별 stop 시퀀스 캐시: {(container_id) → [(stop_id, sequence_no, location_id)]}
    cstop_cache: dict[int, list[ContainerStopModel]] = {}

    legs_processed = 0
    legs_with_extra_charges = 0
    segments_created = 0
    rates_created = 0

    # 이미 leg_rate 박힌 leg 는 skip
    legs_with_rate = (await db.execute(
        select(LegRateModel.leg_id).where(LegRateModel.team_id == team.id)
    )).scalars().all()
    legs_with_rate_set = set(legs_with_rate)

    for leg in legs:
        if leg.id in legs_with_rate_set:
            continue

        # 1) move_type_v3 (마이그레이션이 이미 백필했지만 누락분 보강)
        if leg.move_type_v3 is None:
            leg.move_type_v3 = move_map.get(
                str(leg.move_type.value if hasattr(leg.move_type, "value") else leg.move_type),
                "FULL_LOADED",
            )

        # 2) container_stop 시퀀스 보장 — 한 컨테이너의 첫 leg가 ORIGIN/DELIVERY 만들고,
        #    다음 leg가 DELIVERY/TERMINUS 추가 (간이 모델)
        if leg.container_id is None:
            continue

        if leg.container_id not in cstop_cache:
            cstop_cache[leg.container_id] = (await db.execute(
                select(ContainerStopModel).where(
                    ContainerStopModel.team_id == team.id,
                    ContainerStopModel.container_id == leg.container_id,
                ).order_by(ContainerStopModel.sequence_no.asc())
            )).scalars().all()

        stops = cstop_cache[leg.container_id]

        # from_stop = pickup_location_id 매칭
        from_stop = next((s for s in stops if s.location_id == leg.pickup_location_id), None) \
            if leg.pickup_location_id else None
        if from_stop is None and leg.pickup_location_id:
            seq = (stops[-1].sequence_no + 1) if stops else 1
            role = StopRole.ORIGIN if seq == 1 else StopRole.TRANSIT
            from_stop = ContainerStopModel(
                team_id=team.id,
                container_id=leg.container_id,
                sequence_no=seq,
                role=role,
                location_id=leg.pickup_location_id,
                planned_arrival=leg.pickup_date,
                planned_departure=leg.pickup_date,
                actual_arrival=leg.started_at,
                actual_departure=leg.started_at,
            )
            db.add(from_stop)
            await db.flush()
            stops.append(from_stop)

        # to_stop = delivery_location_id 매칭
        to_stop = next((s for s in stops if s.location_id == leg.delivery_location_id), None) \
            if leg.delivery_location_id else None
        if to_stop is None and leg.delivery_location_id:
            seq = (stops[-1].sequence_no + 1) if stops else 1
            # 마지막이면 TERMINUS, 아니면 DELIVERY
            role = StopRole.DELIVERY  # 단순화 — 마지막 보정은 이후
            to_stop = ContainerStopModel(
                team_id=team.id,
                container_id=leg.container_id,
                sequence_no=seq,
                role=role,
                location_id=leg.delivery_location_id,
                planned_arrival=leg.delivery_date,
                planned_departure=leg.delivery_date,
                actual_arrival=leg.arrived_at,
                actual_departure=leg.completed_at,
            )
            db.add(to_stop)
            await db.flush()
            stops.append(to_stop)

        leg.from_stop_id = from_stop.id if from_stop else None
        leg.to_stop_id   = to_stop.id   if to_stop   else None

        # 3) leg_driver_segment (기존 driver_id 기반 1개)
        if leg.driver_id is not None:
            existing_seg = (await db.execute(
                select(LegDriverSegmentModel).where(
                    LegDriverSegmentModel.team_id == team.id,
                    LegDriverSegmentModel.leg_id == leg.id,
                )
            )).first()
            if not existing_seg:
                db.add(LegDriverSegmentModel(
                    team_id=team.id,
                    leg_id=leg.id,
                    sequence_no=1,
                    driver_id=leg.driver_id,
                    truck_id=leg.truck_id,
                    started_at=leg.started_at,
                    ended_at=leg.completed_at,
                    handover_reason=None,
                ))
                segments_created += 1

        # 4) leg_rate snapshot — RateTariff lookup
        existing_rate = (await db.execute(
            select(LegRateModel).where(
                LegRateModel.team_id == team.id,
                LegRateModel.leg_id == leg.id,
            )
        )).first()
        if not existing_rate:
            tariff = tariff_by_move.get(leg.move_type_v3)
            distance_value = Decimal("0")
            duration_min = Decimal("0")
            if leg.pickup_location_id and leg.delivery_location_id:
                dm = (await db.execute(
                    select(DistanceMatrixModel).where(
                        DistanceMatrixModel.team_id == team.id,
                        DistanceMatrixModel.origin_location_id == leg.pickup_location_id,
                        DistanceMatrixModel.destination_location_id == leg.delivery_location_id,
                    )
                )).scalar_one_or_none()
                if dm:
                    distance_value = dm.distance_value
                    duration_min = dm.duration_min

            base = Decimal("0")
            source = LegRateSource.NONE
            if tariff:
                base = (tariff.flat_base or Decimal("0")) \
                     + (tariff.per_value or Decimal("0")) * distance_value \
                     + (tariff.per_min   or Decimal("0")) * duration_min
                source = LegRateSource.TARIFF_CALC if distance_value > 0 else LegRateSource.TARIFF_FLAT

            db.add(LegRateModel(
                team_id=team.id,
                leg_id=leg.id,
                rate_tariff_id=tariff.id if tariff else None,
                snapshot_distance_value=distance_value,
                snapshot_duration_min=duration_min,
                snapshot_per_value=tariff.per_value if tariff else None,
                snapshot_per_min=tariff.per_min if tariff else None,
                snapshot_flat_base=tariff.flat_base if tariff else None,
                base_amount=base.quantize(Decimal("0.01")),
                source=source,
                payee_driver_id=leg.driver_id,
                computed_at=now_utc(),
            ))
            rates_created += 1

        # 5) 일부 leg에 시나리오 검증용 LegCharge (10번에 1번)
        if legs_processed % 10 == 0 and "WAITING_10MIN" in cc_by_code:
            cc = cc_by_code["WAITING_10MIN"]
            db.add(LegChargeModel(
                team_id=team.id,
                leg_id=leg.id,
                charge_code_id=cc.id,
                snapshot_unit_amount=cc.default_amount,
                quantity=Decimal("3"),
                amount=(cc.default_amount or Decimal("0")) * Decimal("3"),
                source="MANUAL",
                payee_kind="DRIVER",
                payee_driver_id=leg.driver_id,
                description="시나리오 검증: 30분 대기",
            ))
            legs_with_extra_charges += 1

        legs_processed += 1
        if legs_processed % 20 == 0:
            await db.flush()

    await db.flush()
    print(f"[v3 leg backfill] processed={legs_processed} segments={segments_created} rates={rates_created} +charges={legs_with_extra_charges}")


async def seed_v3_container_states(db, team: TeamModel, containers: list[ContainerModel]) -> None:
    """v3 container.work_state 자동 derive (간이):
      - 모든 leg가 COMPLETED → COMPLETED
      - 활성 leg가 IN_TRANSIT → IN_TRANSIT
      - 그 외 PENDING → PLANNED
    """
    from leg.const.status import LegStatus, ContainerState
    derived = 0
    for c in containers:
        legs = (await db.execute(
            select(LegModel).where(
                LegModel.team_id == team.id,
                LegModel.container_id == c.id,
            )
        )).scalars().all()
        if not legs:
            new_state = ContainerState.DRAFT
        elif all(l.status == LegStatus.COMPLETED for l in legs):
            new_state = ContainerState.COMPLETED
        elif any(l.status == LegStatus.IN_TRANSIT for l in legs):
            new_state = ContainerState.IN_TRANSIT
        else:
            new_state = ContainerState.PLANNED
        if c.work_state != new_state:
            c.work_state = new_state
            derived += 1
    if derived:
        await db.flush()
    print(f"[v3 container.work_state] derived={derived}")


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
        drivers = await seed_drivers(db, team, customers)
        trucks = await seed_trucks(db, team, drivers)
        _ = trucks  # noqa: F841 — H-3 단계: leg.truck_id 자동매칭은 H-7 이후
        pools = await seed_equipment_pools(db, team)
        chassis = await seed_chassis(db, team, drivers, pools)
        _ = chassis  # noqa: F841 — leg/container.chassis_id 자동매칭은 H-7 이후
        await seed_rate_settings(db, team)
        charge_codes = await seed_charge_codes(db, team)
        await seed_rate_cards(db, team, charge_codes, customers, terminals)

        delivery_orders, containers = await seed_delivery_orders(db, team, customers, terminals, vessels, locations)
        legs = await seed_legs(db, team, delivery_orders, containers, drivers, locations)
        # H-7: 일부 COMPLETED leg 에 자동 매칭 — rate_card → leg_charge
        from leg_charge.auto_match import auto_match_for_leg
        from leg.const.status import LegStatus as _LegStatus
        completed_legs = [l for l in legs if l.status == _LegStatus.COMPLETED][:20]
        auto_count = 0
        for l in completed_legs:
            created = await auto_match_for_leg(db, team.id, l.id)
            auto_count += len(created)
        print(f"[leg_charge AUTO] {auto_count} (across {len(completed_legs)} legs)")
        await seed_settlements(db, team, legs)
        await seed_street_turns(db, team, delivery_orders, containers, test_user)
        await seed_notifications(db, team, test_user, delivery_orders)
        await seed_api_keys(db, team, test_user)

        # ── v3 Container-First layer ──
        await seed_v3_team_settings(db, team)
        await seed_v3_charge_codes(db, team)
        await seed_v3_distance_matrix(db, team, locations)
        await seed_v3_rate_tariffs(db, team)
        await seed_v3_legs_full(db, team, legs, locations)
        await seed_v3_container_states(db, team, containers)

        await db.commit()

    print("\n=== Demo seed 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())
